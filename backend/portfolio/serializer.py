# serializers.py
from rest_framework import serializers
from .models import Photo

class PhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ['id', 'title', 'description', 'image', 'created_at']

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None