import io
import math
import os

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Label, Photo, extract_camera_settings


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_BULK_UPLOAD_BYTES = 300 * 1024 * 1024
MAX_BULK_UPLOAD_FILES = 25
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
JPEG_UPLOAD_QUALITIES = (90, 85, 80, 75, 70, 65, 60)


def validate_uploaded_image(image):
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


def _flatten_for_jpeg(pil_image):
    if "A" not in pil_image.getbands():
        return pil_image.convert("RGB")

    rgba_image = pil_image.convert("RGBA")
    background = Image.new("RGB", rgba_image.size, "white")
    background.paste(rgba_image, mask=rgba_image.getchannel("A"))
    return background


def _encode_jpeg(pil_image, quality):
    output = io.BytesIO()
    pil_image.save(
        output,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return output.getvalue()


def prepare_uploaded_image_for_storage(image, max_bytes, max_pixels):
    image.seek(0)
    try:
        with Image.open(image) as source_image:
            camera_settings = extract_camera_settings(source_image)
            width, height = source_image.size
            requires_optimization = (
                image.size > max_bytes or width * height > max_pixels
            )
            if not requires_optimization:
                return image, camera_settings, False

            source_image.load()
            working_image = _flatten_for_jpeg(
                ImageOps.exif_transpose(source_image)
            )
    finally:
        image.seek(0)

    pixel_count = working_image.width * working_image.height
    if pixel_count > max_pixels:
        scale = math.sqrt(max_pixels / pixel_count)
        dimensions = (
            max(1, int(working_image.width * scale)),
            max(1, int(working_image.height * scale)),
        )
        working_image = working_image.resize(dimensions, Image.Resampling.LANCZOS)

    margin = min(64 * 1024, max_bytes // 20)
    target_bytes = max_bytes - margin
    while True:
        encoded_image = None
        for quality in JPEG_UPLOAD_QUALITIES:
            encoded_image = _encode_jpeg(working_image, quality)
            if len(encoded_image) <= target_bytes:
                base_name = os.path.splitext(os.path.basename(image.name))[0]
                optimized_upload = SimpleUploadedFile(
                    f"{base_name or 'photo'}.jpg",
                    encoded_image,
                    content_type="image/jpeg",
                )
                return optimized_upload, camera_settings, True

        scale = min(
            0.9,
            math.sqrt(target_bytes / len(encoded_image)) * 0.95,
        )
        dimensions = (
            max(1, int(working_image.width * scale)),
            max(1, int(working_image.height * scale)),
        )
        if dimensions == working_image.size:
            raise forms.ValidationError(
                "This image could not be optimized for storage."
            )
        working_image = working_image.resize(dimensions, Image.Resampling.LANCZOS)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def clean(self, data, initial=None):
        clean_single_file = super().clean
        if isinstance(data, (list, tuple)):
            if not data:
                clean_single_file(None, initial)
            return [clean_single_file(item, initial) for item in data]
        return [clean_single_file(data, initial)]


class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["title", "description", "label", "image"]
        widgets = {
            "image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["label"].label = "Folder"

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image is False:
            raise forms.ValidationError("Photos must keep an image.")
        if self.instance.pk and not self.files.get("image"):
            return image
        return validate_uploaded_image(image)


class PhotoEditForm(PhotoForm):
    class Meta(PhotoForm.Meta):
        fields = ["title", "description", "label", "image"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False
        self.fields["image"].help_text = (
            "Upload a replacement image to refresh previews and camera settings."
        )

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image is False:
            raise forms.ValidationError("Photos must keep an image.")
        if not self.files.get("image"):
            return image
        return validate_uploaded_image(image)


class BulkPhotoUploadForm(forms.Form):
    images = MultipleImageField(
        label="Images",
        help_text="Choose up to 25 JPEG, PNG, or WebP images (300 MB per batch).",
        widget=MultipleFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "multiple": True,
            }
        ),
    )
    label = forms.ModelChoiceField(
        label="Folder",
        queryset=Label.objects.all(),
        required=False,
        empty_label="No folder",
        help_text="Every photo in this upload will start in this folder.",
    )
    title_prefix = forms.CharField(
        max_length=80,
        required=False,
        help_text="Optional. Filenames are converted into individual photo titles.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Optional shared description for every photo in this upload.",
    )

    def clean_images(self):
        images = self.cleaned_data["images"]
        if not images:
            raise forms.ValidationError("Select at least one image.")
        if len(images) > MAX_BULK_UPLOAD_FILES:
            raise forms.ValidationError(
                f"Upload {MAX_BULK_UPLOAD_FILES} images or fewer at once."
            )

        total_size = sum(image.size for image in images)
        if total_size > MAX_BULK_UPLOAD_BYTES:
            raise forms.ValidationError("Upload batches must be 300 MB or smaller.")

        for image in images:
            validate_uploaded_image(image)

        return images


class FolderCreateForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Stockholm streets",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional note about this folder",
                }
            ),
        }
