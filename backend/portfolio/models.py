from django.db import models
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
from PIL import ExifTags, Image, ImageOps


logger = logging.getLogger(__name__)

THUMB_MAX_W = 800     # grid thumbnail
THUMB_QUALITY = 70
PREVIEW_MAX_W = 1600  # detail view
PREVIEW_QUALITY = 80
BLUR_W = 24           # tiny LQIP width (data URL)


def _first_exif_value(exif, *tag_names):
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
    except (AttributeError, OSError, ValueError):
        return {"aperture": "", "iso": "", "shutter_speed": ""}

    if not exif:
        return {"aperture": "", "iso": "", "shutter_speed": ""}

    exposure_time = _first_exif_value(exif, "ExposureTime")
    shutter_speed_value = _first_exif_value(exif, "ShutterSpeedValue")

    return {
        "aperture": _format_aperture(_first_exif_value(exif, "FNumber")),
        "iso": _format_iso(
            _first_exif_value(exif, "ISOSpeedRatings", "PhotographicSensitivity")
        ),
        "shutter_speed": (
            _format_exposure_time(exposure_time)
            or _format_shutter_speed_value(shutter_speed_value)
        ),
    }


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

    # ---------- Derivative helpers ----------
    def _make_resized_jpeg(self, pil_img, max_w, quality):
        # convert to RGB and resize to max width (maintain aspect)
        if pil_img.mode not in ("RGB", "L"):
            pil_img = pil_img.convert("RGB")
        w, h = pil_img.size
        if w > max_w:
            new_h = int(h * (max_w / float(w)))
            pil_img = pil_img.resize((max_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        return buf.getvalue()

    def _build_blur_data_url(self, pil_img, tiny_w=BLUR_W):
        img = pil_img
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        new_h = max(1, int(h * (tiny_w / float(w)))) if w else 1
        tiny = img.resize((tiny_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        tiny.save(buf, format="JPEG", quality=25, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def generate_derivatives(self, force=False):
        """
        Create thumbnail (~800w), preview (~1600w), and blur_data_url.
        Safe to call multiple times; controlled by 'force'.
        """
        if not self.image:
            return

        # Ensure file is readable from storage (S3, etc.)
        self.image.open()
        img = Image.open(self.image)
        img.load()
        display_img = ImageOps.exif_transpose(img.copy())

        # thumbnail
        if force or not self.thumb:
            thumb_bytes = self._make_resized_jpeg(
                display_img.copy(), THUMB_MAX_W, THUMB_QUALITY
            )
            base_name = os.path.basename(self.image.name)
            self.thumb.save(
                os.path.basename(photo_thumb_upload_to(self, base_name)),
                ContentFile(thumb_bytes),
                save=False,
            )
        # preview
        if force or not self.preview:
            preview_bytes = self._make_resized_jpeg(
                display_img.copy(), PREVIEW_MAX_W, PREVIEW_QUALITY
            )
            base_name = os.path.basename(self.image.name)
            self.preview.save(
                os.path.basename(photo_preview_upload_to(self, base_name)),
                ContentFile(preview_bytes),
                save=False,
            )

        # blur data url (tiny)
        if force or not self.blur_data_url:
            self.blur_data_url = self._build_blur_data_url(display_img.copy())

        for field, value in extract_camera_settings(img).items():
            if force or not getattr(self, field):
                setattr(self, field, value)

    def save(self, *args, **kwargs):
        """
        - On first save, set per-label order.
        - Always ensure original is saved first, then generate derivatives,
          then persist derivative fields only to avoid loops.
        """
        is_create = not self.pk
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

        # If the original exists, generate derivatives
        if self.image:
            self.image.open()
            pil = Image.open(self.image)
            pil.load()
            display_pil = ImageOps.exif_transpose(pil.copy())
            derivative_update_fields = []
            should_update_exif = (
                is_create
                or image_changed
                or not (self.aperture and self.iso and self.shutter_speed)
            )

            if should_update_exif:
                for field, value in extract_camera_settings(pil).items():
                    if getattr(self, field) != value:
                        setattr(self, field, value)
                        derivative_update_fields.append(field)

            # thumb
            if not self.thumb:
                tb = self._make_resized_jpeg(
                    display_pil.copy(), THUMB_MAX_W, THUMB_QUALITY
                )
                name = os.path.basename(self.image.name)
                self.thumb.save(
                    os.path.basename(photo_thumb_upload_to(self, name)),
                    ContentFile(tb),
                    save=False,
                )
                derivative_update_fields.append("thumb")

            # preview
            if not self.preview:
                pv = self._make_resized_jpeg(
                    display_pil.copy(), PREVIEW_MAX_W, PREVIEW_QUALITY
                )
                name = os.path.basename(self.image.name)
                self.preview.save(
                    os.path.basename(photo_preview_upload_to(self, name)),
                    ContentFile(pv),
                    save=False,
                )
                derivative_update_fields.append("preview")

            # blur
            if not self.blur_data_url:
                self.blur_data_url = self._build_blur_data_url(display_pil.copy())
                derivative_update_fields.append("blur_data_url")

            # persist only the derivative fields to avoid re-triggering logic
            if derivative_update_fields:
                super().save(update_fields=sorted(set(derivative_update_fields)))

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
