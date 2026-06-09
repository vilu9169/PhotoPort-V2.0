from django.contrib import admin
from django.utils.html import format_html

from .forms import PhotoForm
from .models import Label, Photo


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "order", "photo_count")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-order", "-id")
    def photo_count(self, obj): return obj.photos.count()

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    form = PhotoForm
    list_display = ("id", "thumb", "title", "label", "order")
    list_filter = ("label",)
    search_fields = ("title", "description")
    list_select_related = ("label",)
    ordering = ("-order", "-id")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:60px;object-fit:cover;border-radius:6px;">', obj.image.url)
        return "—"
