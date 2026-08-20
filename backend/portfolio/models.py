from django.conf import settings
from django.db import close_old_connections, models
from django.utils.text import slugify
from django.utils import timezone
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# NEW: imports for derivative generation
import base64
import io
import logging
import os
import threading
from fractions import Fraction
from urllib.parse import urlsplit, urlunsplit
from PIL import ExifTags, Image, ImageOps


logger = logging.getLogger(__name__)

THUMB_MAX_W = 800     # grid thumbnail
THUMB_QUALITY = 70
PREVIEW_MAX_W = 1600  # detail view
PREVIEW_QUALITY = 80
BLUR_W = 24           # tiny LQIP width (data URL)
DERIVATIVE_GENERATION_LOCK = threading.Lock()


def cloudinary_variant_url(url, max_width):
    """Build an on-demand Cloudinary delivery URL without touching the original."""
    if not url:
        return ""

    marker = "/image/upload/"
    parsed = urlsplit(url)
    if marker not in parsed.path:
        return url

    transformation = f"a_auto,c_limit,f_auto,q_auto,w_{int(max_width)}"
    path = parsed.path.replace(marker, f"{marker}{transformation}/", 1)
    return urlunsplit(parsed._replace(path=path))


def _exif_sources(exif):
    sources = []
    try:
        nested_exif = exif.get_ifd(ExifTags.IFD.Exif)
    except (AttributeError, KeyError, TypeError, ValueError):
        nested_exif = None
    if nested_exif:
        sources.append(nested_exif)
    sources.append(exif)
    return sources


def _first_exif_value(exif_sources, *tag_names):
    for exif in exif_sources:
        for tag_id, value in exif.items():
            if ExifTags.TAGS.get(tag_id) in tag_names and value not in (None, ""):
                return value
    return None


def _rational_to_float(value):
    if value is None:
        return None
    if isinstance(value, (tuple, list)) and len(value) == 2:
        numerator, denominator = value
        if not denominator:
            return None
        return float(numerator) / float(denominator)
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _format_decimal(value, places=1):
    return f"{value:.{places}f}".rstrip("0").rstrip(".")


def _format_aperture(value):
    numeric = _rational_to_float(value)
    if not numeric:
        return ""
    return f"f/{_format_decimal(numeric)}"


def _format_aperture_value(value):
    apex = _rational_to_float(value)
    if apex is None:
        return ""
    return _format_aperture(2 ** (apex / 2))


def _format_iso(value):
    if isinstance(value, (tuple, list)):
        value = next((item for item in value if item), None)
    numeric = _rational_to_float(value)
    if not numeric:
        return ""
    return str(int(round(numeric)))


def _format_shutter_seconds(seconds):
    if not seconds:
        return ""
    if seconds >= 1:
        return f"{_format_decimal(seconds, 2)}s"
    fraction = Fraction(seconds).limit_denominator(8000)
    return f"{fraction.numerator}/{fraction.denominator}"


def _format_exposure_time(value):
    if isinstance(value, (tuple, list)) and len(value) == 2:
        numerator, denominator = value
        if numerator and denominator:
            if numerator < denominator:
                return f"{int(numerator)}/{int(denominator)}"
            return _format_shutter_seconds(float(numerator) / float(denominator))
    return _format_shutter_seconds(_rational_to_float(value))


def _format_shutter_speed_value(value):
    apex = _rational_to_float(value)
    if apex is None:
        return ""
    return _format_shutter_seconds(2 ** (-apex))


def extract_camera_settings(pil_img):
    try:
        exif = pil_img.getexif()
        if not exif:
            return {"aperture": "", "iso": "", "shutter_speed": ""}

        exif_sources = _exif_sources(exif)
        exposure_time = _first_exif_value(exif_sources, "ExposureTime")
        shutter_speed_value = _first_exif_value(
            exif_sources,
            "ShutterSpeedValue",
        )
        aperture = _format_aperture(
            _first_exif_value(exif_sources, "FNumber")
        ) or _format_aperture_value(
            _first_exif_value(exif_sources, "ApertureValue")
        )

        return {
            "aperture": aperture,
            "iso": _format_iso(
                _first_exif_value(
                    exif_sources,
                    "ISOSpeedRatings",
                    "PhotographicSensitivity",
                    "ISOSpeed",
                    "StandardOutputSensitivity",
                    "RecommendedExposureIndex",
                )
            ),
            "shutter_speed": (
                _format_exposure_time(exposure_time)
                or _format_shutter_speed_value(shutter_speed_value)
            ),
        }
    except (
        AttributeError,
        OSError,
        OverflowError,
        TypeError,
        ValueError,
        ZeroDivisionError,
    ):
        logger.warning("Unable to read camera settings from image EXIF", exc_info=True)
        return {"aperture": "", "iso": "", "shutter_speed": ""}


def photo_upload_to(instance, filename):
    """
    Store new uploads under photos/<label-slug>/<YYYY>/<MM>/<filename>
    or photos/<YYYY>/<MM>/<filename> if no label is set.
    """
    date = timezone.now()
    if getattr(instance, "label_id", None) and instance.label:
        return f"photos/{instance.label.slug}/{date:%Y/%m}/{filename}"
    return f"photos/{date:%Y/%m}/{filename}"


def photo_thumb_upload_to(instance, filename):
    date = timezone.now()
    name, _ = os.path.splitext(os.path.basename(filename))
    if getattr(instance, "label_id", None) and instance.label:
        return f"photos/{instance.label.slug}/{date:%Y/%m}/thumbs/{name}.jpg"
    return f"photos/{date:%Y/%m}/thumbs/{name}.jpg"


def photo_preview_upload_to(instance, filename):
    date = timezone.now()
    name, _ = os.path.splitext(os.path.basename(filename))
    if getattr(instance, "label_id", None) and instance.label:
        return f"photos/{instance.label.slug}/{date:%Y/%m}/previews/{name}.jpg"
    return f"photos/{date:%Y/%m}/previews/{name}.jpg"


class Label(models.Model):
    title = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order", "-id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Photo(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to=photo_upload_to)  # original

    # NEW: stored derivatives
    thumb = models.ImageField(upload_to=photo_thumb_upload_to, blank=True, null=True)
    preview = models.ImageField(upload_to=photo_preview_upload_to, blank=True, null=True)

    # NEW: optional tiny base64 placeholder for blur-up
    blur_data_url = models.TextField(blank=True, default="")

    aperture = models.CharField(max_length=20, blank=True, default="")
    iso = models.CharField(max_length=20, blank=True, default="")
    shutter_speed = models.CharField(max_length=30, blank=True, default="")

    # optional grouping
    label = models.ForeignKey(
        Label,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="photos",
    )

    category = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.IntegerField(default=0)

    class Meta:
        # default list order; we keep newest/highest order first
        ordering = ["-order", "-id"]
        indexes = [
            models.Index(fields=["label", "-order"]),
        ]

    def __str__(self):
        return self.title

    @staticmethod
    def _field_url(file_field):
        if not file_field:
            return ""
        try:
            return file_field.url
        except (AttributeError, ValueError):
            return ""

    @property
    def thumbnail_url(self):
        stored_url = self._field_url(self.thumb)
        if stored_url:
            return stored_url

        original_url = self._field_url(self.image)
        if settings.USE_CLOUDINARY:
            return cloudinary_variant_url(original_url, THUMB_MAX_W)
        return original_url

    @property
    def preview_url(self):
        stored_url = self._field_url(self.preview)
        if stored_url:
            return stored_url

        original_url = self._field_url(self.image)
        if settings.USE_CLOUDINARY:
            return cloudinary_variant_url(original_url, PREVIEW_MAX_W)
        return original_url

    # ---------- Derivative helpers ----------
    def _make_resized_jpeg(self, pil_img, max_w, quality):
        working_image = pil_img
        owned_images = []
        try:
            if working_image.mode not in ("RGB", "L"):
                working_image = working_image.convert("RGB")
                owned_images.append(working_image)
            width, height = working_image.size
            if width > max_w:
                resized_image = working_image.resize(
                    (max_w, max(1, int(height * (max_w / float(width))))),
                    Image.Resampling.LANCZOS,
                )
                owned_images.append(resized_image)
                working_image = resized_image
            with io.BytesIO() as buffer:
                working_image.save(
                    buffer,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=True,
                )
                return buffer.getvalue()
        finally:
            for owned_image in owned_images:
                owned_image.close()

    def _build_blur_data_url(self, pil_img, tiny_w=BLUR_W):
        working_image = pil_img
        converted_image = None
        tiny_image = None
        try:
            if working_image.mode not in ("RGB", "L"):
                converted_image = working_image.convert("RGB")
                working_image = converted_image
            width, height = working_image.size
            new_height = (
                max(1, int(height * (tiny_w / float(width)))) if width else 1
            )
            tiny_image = working_image.resize(
                (tiny_w, new_height),
                Image.Resampling.LANCZOS,
            )
            with io.BytesIO() as buffer:
                tiny_image.save(buffer, format="JPEG", quality=25, optimize=True)
                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                return f"data:image/jpeg;base64,{encoded}"
        finally:
            if tiny_image is not None:
                tiny_image.close()
            if converted_image is not None:
                converted_image.close()

    def generate_derivatives(self, force=False):
        """
        Create thumbnail (~800w), preview (~1600w), and blur_data_url.
        Safe to call multiple times; controlled by 'force'.
        """
        if not self.image or settings.USE_CLOUDINARY:
            return

        with DERIVATIVE_GENERATION_LOCK:
            self.image.open()
            try:
                with Image.open(self.image) as source_image:
                    camera_settings = extract_camera_settings(source_image)

                    # JPEG draft decoding avoids allocating the full-resolution
                    # raster when only 1600px derivatives are needed.
                    source_image.draft(
                        "RGB",
                        (PREVIEW_MAX_W, PREVIEW_MAX_W),
                    )
                    source_image.thumbnail(
                        (PREVIEW_MAX_W, PREVIEW_MAX_W),
                        Image.Resampling.LANCZOS,
                    )
                    display_image = ImageOps.exif_transpose(source_image)
                    try:
                        display_image.load()
                        base_name = os.path.basename(self.image.name)

                        if force or not self.thumb:
                            thumb_bytes = self._make_resized_jpeg(
                                display_image,
                                THUMB_MAX_W,
                                THUMB_QUALITY,
                            )
                            self.thumb.save(
                                os.path.basename(
                                    photo_thumb_upload_to(self, base_name)
                                ),
                                ContentFile(thumb_bytes),
                                save=False,
                            )

                        if force or not self.preview:
                            preview_bytes = self._make_resized_jpeg(
                                display_image,
                                PREVIEW_MAX_W,
                                PREVIEW_QUALITY,
                            )
                            self.preview.save(
                                os.path.basename(
                                    photo_preview_upload_to(self, base_name)
                                ),
                                ContentFile(preview_bytes),
                                save=False,
                            )

                        if force or not self.blur_data_url:
                            self.blur_data_url = self._build_blur_data_url(
                                display_image
                            )
                    finally:
                        if display_image is not source_image:
                            display_image.close()

                    for field, value in camera_settings.items():
                        if force or not getattr(self, field):
                            setattr(self, field, value)
            finally:
                self.image.close()

    def save(self, *args, **kwargs):
        """
        - On first save, set per-label order.
        - Save EXIF with the original.
        - Generate derivatives immediately unless the caller explicitly defers them.
        """
        is_create = not self.pk
        defer_derivatives = (
            getattr(self, "_defer_derivatives", False)
            or settings.USE_CLOUDINARY
        )
        previous_files = None
        image_changed = False

        if self.pk:
            previous = (
                Photo.objects.filter(pk=self.pk)
                .only("image", "thumb", "preview")
                .first()
            )
            if previous:
                previous_files = (previous.image, previous.thumb, previous.preview)
                image_changed = previous.image.name != getattr(self.image, "name", "")

        if image_changed:
            self.thumb = None
            self.preview = None
            self.blur_data_url = ""
            self.aperture = ""
            self.iso = ""
            self.shutter_speed = ""
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {
                    "thumb",
                    "preview",
                    "blur_data_url",
                    "aperture",
                    "iso",
                    "shutter_speed",
                }

        if is_create:
            qs = Photo.objects.filter(label=self.label)
            max_order = qs.aggregate(models.Max("order"))["order__max"]
            self.order = (max_order or 0) + 1

        if defer_derivatives and self.image and (is_create or image_changed):
            self.image.open()
            try:
                with Image.open(self.image) as pil:
                    for field, value in extract_camera_settings(pil).items():
                        if value or not getattr(self, field):
                            setattr(self, field, value)
            finally:
                self.image.seek(0)

        # save original (and any field changes)
        super().save(*args, **kwargs)

        if image_changed and previous_files:
            current_names = {
                getattr(field, "name", "")
                for field in (self.image, self.thumb, self.preview)
                if field
            }
            for file_field in previous_files:
                if (
                    file_field
                    and file_field.name
                    and file_field.name not in current_names
                ):
                    file_field.delete(save=False)

        # If the original exists, generate derivatives.
        if self.image and not defer_derivatives:
            self.generate_derivatives()
            super().save(
                update_fields=[
                    "thumb",
                    "preview",
                    "blur_data_url",
                    "aperture",
                    "iso",
                    "shutter_speed",
                ]
            )


def generate_photo_derivatives(photo_ids):
    close_old_connections()
    try:
        for photo_id in photo_ids:
            try:
                photo = Photo.objects.get(pk=photo_id)
            except Photo.DoesNotExist:
                continue

            try:
                photo.generate_derivatives()
            except Exception:
                logger.exception("Unable to generate derivatives for photo %s", photo_id)
            updates = {}
            if photo.thumb and photo.thumb.name:
                updates["thumb"] = photo.thumb.name
            if photo.preview and photo.preview.name:
                updates["preview"] = photo.preview.name
            if photo.blur_data_url:
                updates["blur_data_url"] = photo.blur_data_url
            for field in ("aperture", "iso", "shutter_speed"):
                value = getattr(photo, field)
                if value:
                    updates[field] = value
            if updates:
                try:
                    Photo.objects.filter(pk=photo_id).update(**updates)
                except Exception:
                    logger.exception(
                        "Unable to persist derivatives for photo %s",
                        photo_id,
                    )
    finally:
        close_old_connections()


def schedule_photo_derivative_generation(photo_ids):
    ids = tuple(dict.fromkeys(photo_id for photo_id in photo_ids if photo_id))
    if not ids:
        return

    derivative_thread = threading.Thread(
        target=generate_photo_derivatives,
        args=(ids,),
        name="photo-derivative-generation",
        daemon=True,
    )
    derivative_thread.start()


@receiver(post_delete, sender=Photo)
def delete_file_from_storage_on_delete(sender, instance, **kwargs):
    """Remove files from configured storage when a Photo row is deleted."""
    if getattr(instance, "_defer_storage_cleanup", False):
        return

    delete_storage_files(
        field.name
        for field in (instance.image, instance.thumb, instance.preview)
        if field and field.name
    )


def delete_storage_files(storage_names):
    for storage_name in dict.fromkeys(storage_names):
        try:
            default_storage.delete(storage_name)
        except Exception:
            logger.exception("Unable to delete stored photo file %s", storage_name)


def schedule_storage_file_deletion(storage_names):
    names = tuple(dict.fromkeys(name for name in storage_names if name))
    if not names:
        return

    cleanup_thread = threading.Thread(
        target=delete_storage_files,
        args=(names,),
        name="photo-storage-cleanup",
        daemon=True,
    )
    cleanup_thread.start()
