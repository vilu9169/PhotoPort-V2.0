from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.db.models.signals import post_delete
from django.dispatch import receiver

# NEW: imports for derivative generation
import io, os, base64
from PIL import Image


THUMB_MAX_W = 800     # grid thumbnail
THUMB_QUALITY = 70
PREVIEW_MAX_W = 1600  # detail view
PREVIEW_QUALITY = 80
BLUR_W = 24           # tiny LQIP width (data URL)


def photo_upload_to(instance, filename):
    """
    Store new uploads under photos/<folder-slug>/<YYYY>/<MM>/<filename>
    or photos/<YYYY>/<MM>/<filename> if no folder is set.
    """
    date = timezone.now()
    if getattr(instance, "folder_id", None) and instance.folder:
        return f"photos/{instance.folder.slug}/{date:%Y/%m}/{filename}"
    return f"photos/{date:%Y/%m}/{filename}"


def photo_thumb_upload_to(instance, filename):
    date = timezone.now()
    name, _ = os.path.splitext(os.path.basename(filename))
    if getattr(instance, "folder_id", None) and instance.folder:
        return f"photos/{instance.folder.slug}/{date:%Y/%m}/thumbs/{name}.jpg"
    return f"photos/{date:%Y/%m}/thumbs/{name}.jpg"


def photo_preview_upload_to(instance, filename):
    date = timezone.now()
    name, _ = os.path.splitext(os.path.basename(filename))
    if getattr(instance, "folder_id", None) and instance.folder:
        return f"photos/{instance.folder.slug}/{date:%Y/%m}/previews/{name}.jpg"
    return f"photos/{date:%Y/%m}/previews/{name}.jpg"


class Folder(models.Model):
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

    # optional grouping
    folder = models.ForeignKey(
        Folder,
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
            models.Index(fields=["folder", "-order"]),
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

        # thumbnail
        if force or not self.thumb:
            thumb_bytes = self._make_resized_jpeg(img.copy(), THUMB_MAX_W, THUMB_QUALITY)
            base_name = os.path.basename(self.image.name)
            self.thumb.save(
                os.path.basename(photo_thumb_upload_to(self, base_name)),
                models.FileField().to_python(io.BytesIO(thumb_bytes)) or models.FileField(),
                save=False,
            )
            # Using ContentFile is clearer; see below (we’ll import it)
        # preview
        if force or not self.preview:
            preview_bytes = self._make_resized_jpeg(img.copy(), PREVIEW_MAX_W, PREVIEW_QUALITY)
            base_name = os.path.basename(self.image.name)
            self.preview.save(
                os.path.basename(photo_preview_upload_to(self, base_name)),
                models.FileField().to_python(io.BytesIO(preview_bytes)) or models.FileField(),
                save=False,
            )

        # blur data url (tiny)
        if force or not self.blur_data_url:
            self.blur_data_url = self._build_blur_data_url(img)

    def save(self, *args, **kwargs):
        """
        - On first save, set per-folder order.
        - Always ensure original is saved first, then generate derivatives,
          then persist derivative fields only to avoid loops.
        """
        is_create = not self.pk

        if is_create:
            qs = Photo.objects.filter(folder=self.folder)
            max_order = qs.aggregate(models.Max("order"))["order__max"]
            self.order = (max_order or 0) + 1

        # save original (and any field changes)
        super().save(*args, **kwargs)

        # If the original exists, generate derivatives
        if self.image:
            # We use ContentFile for clarity and S3-compatibility
            from django.core.files.base import ContentFile

            self.image.open()
            pil = Image.open(self.image)
            pil.load()

            # thumb
            if not self.thumb:
                tb = self._make_resized_jpeg(pil.copy(), THUMB_MAX_W, THUMB_QUALITY)
                name = os.path.basename(self.image.name)
                self.thumb.save(os.path.basename(photo_thumb_upload_to(self, name)), ContentFile(tb), save=False)

            # preview
            if not self.preview:
                pv = self._make_resized_jpeg(pil.copy(), PREVIEW_MAX_W, PREVIEW_QUALITY)
                name = os.path.basename(self.image.name)
                self.preview.save(os.path.basename(photo_preview_upload_to(self, name)), ContentFile(pv), save=False)

            # blur
            if not self.blur_data_url:
                self.blur_data_url = self._build_blur_data_url(pil)

            # persist only the derivative fields to avoid re-triggering logic
            super().save(update_fields=["thumb", "preview", "blur_data_url"])

@receiver(post_delete, sender=Photo)
def delete_file_from_storage_on_delete(sender, instance, **kwargs):
    """Remove the S3 objects when a Photo row is deleted."""
    # original
    if getattr(instance, "image", None):
        instance.image.delete(save=False)
    # NEW: derivatives
    if getattr(instance, "thumb", None):
        instance.thumb.delete(save=False)
    if getattr(instance, "preview", None):
        instance.preview.delete(save=False)
