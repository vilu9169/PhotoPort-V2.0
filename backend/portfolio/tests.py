import io
from unittest.mock import patch

from django.db import OperationalError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .forms import MAX_UPLOAD_BYTES, PhotoForm
from .models import Label, Photo


def image_upload(name="photo.jpg", image_format="JPEG", size=(32, 32)):
    output = io.BytesIO()
    Image.new("RGB", size, color="white").save(output, format=image_format)
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


class PhotoSecurityTests(TestCase):
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
