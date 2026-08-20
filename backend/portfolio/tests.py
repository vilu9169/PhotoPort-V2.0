import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import ExifTags, Image

from .forms import MAX_UPLOAD_BYTES, BulkPhotoUploadForm, PhotoForm
from .models import (
    Label,
    Photo,
    extract_camera_settings,
    generate_photo_derivatives,
)


def image_upload(name="photo.jpg", image_format="JPEG", size=(32, 32), exif=None):
    output = io.BytesIO()
    save_kwargs = {}
    if exif:
        image_exif = Image.Exif()
        camera_ifd = image_exif.get_ifd(ExifTags.IFD.Exif)
        for tag, value in exif.items():
            camera_ifd[tag] = value
        save_kwargs["exif"] = image_exif
    Image.new("RGB", size, color="white").save(
        output,
        format=image_format,
        **save_kwargs,
    )
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


def noisy_image_upload(name="large-photo.jpg", size=(1000, 800), exif=None):
    output = io.BytesIO()
    save_kwargs = {"quality": 100}
    if exif:
        image_exif = Image.Exif()
        camera_ifd = image_exif.get_ifd(ExifTags.IFD.Exif)
        for tag, value in exif.items():
            camera_ifd[tag] = value
        save_kwargs["exif"] = image_exif
    Image.effect_noise(size, 100).convert("RGB").save(
        output,
        format="JPEG",
        **save_kwargs,
    )
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type="image/jpeg",
    )


class PhotoSecurityTests(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

    def login_staff(self):
        user = get_user_model().objects.create_user(
            username="staff",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        return user

    def test_health_reports_database_available(self):
        response = self.client.get("/health/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "ok")

    @patch(
        "backend.urls.connection.cursor",
        side_effect=OperationalError("database unavailable"),
    )
    def test_health_reports_database_failure(self, mocked_cursor):
        response = self.client.get("/health/", secure=True)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "unavailable")

    def test_anonymous_user_cannot_access_upload_page(self):
        response = self.client.get(reverse("upload_photo"), secure=True)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_anonymous_user_cannot_access_folder_manager(self):
        label = Label.objects.create(title="Private", slug="private")

        response = self.client.get(
            reverse("label_detail", args=[label.slug]),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_api_clamps_negative_pagination_values(self):
        response = self.client.get(
            reverse("photo_list_api"),
            {"limit": "-20", "offset": "-100"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta"]["limit"], 1)
        self.assertEqual(response.json()["meta"]["offset"], 0)
        self.assertIn("public", response["Cache-Control"])

    def test_api_includes_label_metadata(self):
        label = Label.objects.create(title="Japan", slug="japan", order=4)
        photo = Photo(
            title="Tokyo",
            description="Night street",
            label=label,
            aperture="f/2.8",
            iso="400",
            shutter_speed="1/250",
            image="photos/japan/tokyo.jpg",
            thumb="photos/japan/thumbs/tokyo.jpg",
            preview="photos/japan/previews/tokyo.jpg",
        )
        Photo.objects.bulk_create([photo])

        response = self.client.get(reverse("photo_list_api"), secure=True)
        item = response.json()["results"][0]

        self.assertEqual(item["label_title"], "Japan")
        self.assertEqual(item["label_slug"], "japan")
        self.assertEqual(item["label_order"], 4)
        self.assertEqual(item["folder_title"], "Japan")
        self.assertEqual(item["aperture"], "f/2.8")
        self.assertEqual(item["iso"], "400")
        self.assertEqual(item["shutter_speed"], "1/250")

    def test_photo_form_accepts_supported_image(self):
        form = PhotoForm(
            data={"title": "Test", "description": "Test photo"},
            files={"image": image_upload()},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_photo_form_rejects_oversized_upload(self):
        valid_image = image_upload().read()
        upload = SimpleUploadedFile(
            "large.jpg",
            valid_image + b"\0" * (MAX_UPLOAD_BYTES + 1 - len(valid_image)),
            content_type="image/jpeg",
        )
        form = PhotoForm(
            data={"title": "Test", "description": "Test photo"},
            files={"image": upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("20 MB or smaller", form.errors["image"][0])

    def test_photo_form_rejects_unsupported_image_format(self):
        form = PhotoForm(
            data={"title": "Test", "description": "Test photo"},
            files={"image": image_upload("photo.gif", "GIF")},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Only JPEG, PNG, and WebP", form.errors["image"][0])

    def test_photo_save_extracts_camera_settings_from_exif(self):
        photo = Photo.objects.create(
            title="Manual",
            description="EXIF image",
            image=image_upload(
                exif={
                    33434: (1, 250),  # ExposureTime
                    33437: (28, 10),  # FNumber
                    34855: 400,  # ISOSpeedRatings
                }
            ),
        )

        self.assertEqual(photo.aperture, "f/2.8")
        self.assertEqual(photo.iso, "400")
        self.assertEqual(photo.shutter_speed, "1/250")

    def test_photo_save_extracts_modern_camera_setting_fallbacks(self):
        photo = Photo.objects.create(
            title="Modern EXIF",
            description="",
            image=image_upload(
                exif={
                    37377: (8, 1),  # ShutterSpeedValue
                    37378: (3, 1),  # ApertureValue
                    34867: 125,  # ISOSpeed
                }
            ),
        )

        self.assertEqual(photo.aperture, "f/2.8")
        self.assertEqual(photo.iso, "125")
        self.assertEqual(photo.shutter_speed, "1/256")

    def test_bulk_photo_upload_form_accepts_multiple_images(self):
        form = BulkPhotoUploadForm(
            data={"description": "Batch"},
            files={"images": [image_upload("one.jpg"), image_upload("two.jpg")]},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["images"]), 2)

    @patch("portfolio.views.schedule_photo_derivative_generation")
    def test_staff_can_bulk_upload_photos(self, schedule_derivatives):
        label = Label.objects.create(title="Japan", slug="japan", order=4)
        self.login_staff()

        response = self.client.post(
            reverse("upload_photo"),
            data={
                "label": label.id,
                "title_prefix": "Trip",
                "description": "Batch upload",
                "images": [
                    image_upload(
                        "first-photo.jpg",
                        exif={
                            33434: (1, 125),
                            33437: (4, 1),
                            34855: 800,
                        },
                    ),
                    image_upload("second-photo.jpg"),
                ],
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Photo.objects.count(), 2)

        first = Photo.objects.get(title="Trip - First Photo")
        self.assertEqual(first.label, label)
        self.assertEqual(first.description, "Batch upload")
        self.assertEqual(first.aperture, "f/4")
        self.assertEqual(first.iso, "800")
        self.assertEqual(first.shutter_speed, "1/125")
        self.assertFalse(first.thumb)
        self.assertFalse(first.preview)
        schedule_derivatives.assert_called_once()
        self.assertCountEqual(
            schedule_derivatives.call_args.args[0],
            Photo.objects.values_list("id", flat=True),
        )

    def test_deferred_derivatives_are_generated_and_persisted(self):
        photo = Photo(
            title="Deferred",
            description="",
            image=image_upload(
                exif={
                    33434: (1, 200),
                    33437: (28, 10),
                    34855: 320,
                }
            ),
        )
        photo._defer_derivatives = True
        photo.save()

        self.assertFalse(photo.thumb)
        self.assertFalse(photo.preview)
        self.assertEqual(photo.iso, "320")

        generate_photo_derivatives([photo.pk])
        photo.refresh_from_db()

        self.assertTrue(photo.thumb)
        self.assertTrue(photo.preview)
        self.assertTrue(photo.blur_data_url.startswith("data:image/jpeg;base64,"))
        self.assertEqual(photo.aperture, "f/2.8")
        self.assertEqual(photo.shutter_speed, "1/200")

    @patch("portfolio.views.schedule_photo_derivative_generation")
    def test_bulk_upload_continues_after_one_file_fails(
        self,
        schedule_derivatives,
    ):
        self.login_staff()
        original_save = Photo.save

        def fail_one_upload(photo, *args, **kwargs):
            if photo.title == "Broken":
                raise OSError("storage unavailable")
            return original_save(photo, *args, **kwargs)

        with patch.object(Photo, "save", new=fail_one_upload):
            response = self.client.post(
                reverse("upload_photo"),
                data={
                    "description": "Partial batch",
                    "images": [
                        image_upload("broken.jpg"),
                        image_upload("working.jpg"),
                    ],
                },
                secure=True,
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Photo.objects.count(), 1)
        self.assertEqual(Photo.objects.get().title, "Working")
        self.assertContains(response, "Could not upload 1 file: broken.jpg.")
        schedule_derivatives.assert_called_once()

    @override_settings(
        USE_CLOUDINARY=True,
        CLOUDINARY_MAX_IMAGE_BYTES=120 * 1024,
        CLOUDINARY_MAX_IMAGE_PIXELS=400_000,
    )
    @patch("portfolio.views.schedule_photo_derivative_generation")
    def test_cloudinary_bulk_upload_optimizes_oversized_image(
        self,
        schedule_derivatives,
    ):
        self.login_staff()
        upload = noisy_image_upload(
            exif={
                33434: (1, 320),
                33437: (28, 10),
                34855: 640,
            }
        )
        self.assertGreater(upload.size, 120 * 1024)

        response = self.client.post(
            reverse("upload_photo"),
            data={"description": "Optimized", "images": [upload]},
            secure=True,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        photo = Photo.objects.get()
        self.assertLessEqual(photo.image.size, 120 * 1024)
        photo.image.open()
        with Image.open(photo.image) as stored_image:
            self.assertLessEqual(stored_image.width * stored_image.height, 400_000)
            self.assertEqual(
                extract_camera_settings(stored_image),
                {
                    "aperture": "f/2.8",
                    "iso": "640",
                    "shutter_speed": "1/320",
                },
            )
        self.assertEqual(photo.aperture, "f/2.8")
        self.assertEqual(photo.iso, "640")
        self.assertEqual(photo.shutter_speed, "1/320")
        self.assertContains(response, "Optimized 1 oversized photo for Cloudinary.")
        schedule_derivatives.assert_called_once_with([photo.pk])

    def test_staff_can_remove_photo_from_folder(self):
        label = Label.objects.create(title="Japan", slug="japan", order=4)
        photo = Photo.objects.create(
            title="Tokyo",
            description="Street",
            label=label,
            image=image_upload(),
        )
        self.login_staff()

        response = self.client.post(
            reverse("remove_label", args=[photo.id]),
            secure=True,
        )
        photo.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(photo.label)

    def test_staff_can_create_folder_with_unique_slug(self):
        Label.objects.create(title="Existing", slug="stockholm-streets")
        self.login_staff()

        response = self.client.post(
            reverse("create_folder"),
            data={
                "title": "Stockholm streets",
                "description": "Evening walks",
            },
            secure=True,
        )

        folder = Label.objects.get(title="Stockholm streets")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(folder.slug, "stockholm-streets-2")
        self.assertEqual(folder.description, "Evening walks")
        self.assertEqual(response["Location"], reverse("label_detail", args=[folder.slug]))

    def test_photo_manager_renders_folder_and_bulk_controls(self):
        Label.objects.create(title="City", slug="city")
        self.login_staff()

        response = self.client.get(reverse("photo_list"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New folder")
        self.assertContains(response, "Edit selected")
        self.assertContains(response, "Delete selected")
        self.assertContains(response, "City")

    def test_staff_can_bulk_edit_selected_photos(self):
        source = Label.objects.create(title="Inbox", slug="inbox")
        target = Label.objects.create(title="Portfolio", slug="portfolio")
        photos = Photo.objects.bulk_create(
            [
                Photo(
                    title="One",
                    description="Old",
                    label=source,
                    image="photos/one.jpg",
                    order=2,
                ),
                Photo(
                    title="Two",
                    description="Old",
                    label=source,
                    image="photos/two.jpg",
                    order=1,
                ),
                Photo(
                    title="Three",
                    description="Keep",
                    label=source,
                    image="photos/three.jpg",
                    order=3,
                ),
            ]
        )
        self.login_staff()

        response = self.client.post(
            reverse("bulk_photos"),
            data={
                "photo_ids": [photos[0].id, photos[1].id],
                "action": "edit",
                "folder": str(target.id),
                "replace_description": "on",
                "description": "Published set",
            },
            secure=True,
        )

        for photo in photos:
            photo.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(photos[0].label, target)
        self.assertEqual(photos[1].label, target)
        self.assertEqual(photos[0].description, "Published set")
        self.assertEqual(photos[1].description, "Published set")
        self.assertEqual(photos[2].label, source)
        self.assertEqual(photos[2].description, "Keep")

    def test_staff_can_bulk_remove_folder(self):
        label = Label.objects.create(title="Inbox", slug="inbox")
        photos = Photo.objects.bulk_create(
            [
                Photo(
                    title="One",
                    description="",
                    label=label,
                    image="photos/one.jpg",
                ),
                Photo(
                    title="Two",
                    description="",
                    label=label,
                    image="photos/two.jpg",
                ),
            ]
        )
        self.login_staff()

        response = self.client.post(
            reverse("bulk_photos"),
            data={
                "photo_ids": [photo.id for photo in photos],
                "action": "edit",
                "folder": "__none__",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Photo.objects.filter(label=label).exists())
        self.assertEqual(Photo.objects.filter(label__isnull=True).count(), 2)

    @patch("portfolio.views.schedule_storage_file_deletion")
    def test_staff_can_bulk_delete_only_selected_photos(self, schedule_cleanup):
        label = Label.objects.create(title="Inbox", slug="inbox")
        photos = Photo.objects.bulk_create(
            [
                Photo(
                    title="One",
                    description="",
                    label=label,
                    image="photos/one.jpg",
                    order=3,
                ),
                Photo(
                    title="Two",
                    description="",
                    label=label,
                    image="photos/two.jpg",
                    order=2,
                ),
                Photo(
                    title="Three",
                    description="",
                    label=label,
                    image="photos/three.jpg",
                    order=1,
                ),
            ]
        )
        self.login_staff()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("bulk_photos"),
                data={
                    "photo_ids": [photos[0].id, photos[2].id],
                    "action": "delete",
                },
                secure=True,
            )

        photos[1].refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Photo.objects.count(), 1)
        self.assertEqual(photos[1].order, 1)
        schedule_cleanup.assert_called_once()
        self.assertCountEqual(
            schedule_cleanup.call_args.args[0],
            ["photos/one.jpg", "photos/three.jpg"],
        )

    def test_storage_failure_does_not_block_photo_delete(self):
        photo = Photo.objects.bulk_create(
            [
                Photo(
                    title="Unavailable file",
                    description="",
                    image="photos/unavailable.jpg",
                )
            ]
        )[0]
        photo_id = photo.id

        with (
            patch(
                "portfolio.models.default_storage.delete",
                side_effect=OSError("storage unavailable"),
            ),
            self.assertLogs("portfolio.models", level="ERROR"),
        ):
            photo.delete()

        self.assertFalse(Photo.objects.filter(id=photo_id).exists())
