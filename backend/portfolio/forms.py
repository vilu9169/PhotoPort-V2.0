from django import forms
from PIL import Image, UnidentifiedImageError

from .models import Photo


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["title", "description", "label", "image"]

    def clean_image(self):
        image = self.cleaned_data["image"]

        if image.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("Images must be 20 MB or smaller.")

        try:
            image.seek(0)
            with Image.open(image) as pil_image:
                if pil_image.format not in ALLOWED_IMAGE_FORMATS:
                    raise forms.ValidationError(
                        "Only JPEG, PNG, and WebP images are accepted."
                    )
                width, height = pil_image.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise forms.ValidationError(
                        "Images must contain no more than 40 megapixels."
                    )
                pil_image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise forms.ValidationError("Upload a valid, non-corrupted image.")
        finally:
            image.seek(0)

        return image
