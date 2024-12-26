from django.db import models

# Create your models here.

class Photo(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='photos/')
    category = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['-order']  # Always order by the `order` field
    def save(self, *args, **kwargs):
        # If this is a new photo, set the order to the highest current order + 1
        if not self.pk:  # Check if this is a new instance
            max_order = Photo.objects.aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)
    def __str__(self):
        return self.title
    