# serializers.py
from rest_framework import serializers
from .models import Photo

class PhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    folder_title = serializers.CharField(source="folder.title", read_only=True)
    folder_slug = serializers.CharField(source="folder.slug", read_only=True)
    folder_order = serializers.IntegerField(source="folder.order", read_only=True)

    class Meta:
        model = Photo
        fields = [
            "id",
            "title",
            "description",
            "category",
            "created_at",
            "order",
            "image_url",
            "thumbnail_url",
            "preview_url",
            "blur_data_url",
            "folder",
            "folder_title",
            "folder_slug",
            "folder_order",
        ]

    def _abs_url(self, file_field):
        request = self.context.get("request")
        if not file_field:
            return None
        url = getattr(file_field, "url", None)
        if not url:
            return None
        return request.build_absolute_uri(url) if request else url

    def get_image_url(self, obj):
        return self._abs_url(obj.image)

    def get_thumbnail_url(self, obj):
        return self._abs_url(obj.thumb)

    def get_preview_url(self, obj):
        return self._abs_url(obj.preview)
