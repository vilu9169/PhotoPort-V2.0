from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.db.models.signals import post_delete
from django.dispatch import receiver


def photo_upload_to(instance, filename):
    """
    Store new uploads under photos/<folder-slug>/<YYYY>/<MM>/<filename>
    or photos/<YYYY>/<MM>/<filename> if no folder is set.
    """
    date = timezone.now()
    if getattr(instance, "folder_id", None) and instance.folder:
        return f"photos/{instance.folder.slug}/{date:%Y/%m}/{filename}"
    return f"photos/{date:%Y/%m}/{filename}"


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
    image = models.ImageField(upload_to=photo_upload_to)  # was "photos/%Y/%m/"

    # NEW: optional grouping
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

    def save(self, *args, **kwargs):
        """
        On first save, set order to highest current order + 1 *within the same folder*
        (or among ungrouped photos if folder is null).
        """
        if not self.pk:
            qs = Photo.objects.filter(folder=self.folder)
            max_order = qs.aggregate(models.Max("order"))["order__max"]
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)


@receiver(post_delete, sender=Photo)
def delete_file_from_storage_on_delete(sender, instance, **kwargs):
    """Remove the S3 object when a Photo row is deleted."""
    if getattr(instance, "image", None):
        instance.image.delete(save=False)
