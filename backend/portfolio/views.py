import logging
import os

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, transaction
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.utils.text import slugify
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_POST

from .models import (
    Label,
    Photo,
    schedule_photo_derivative_generation,
    schedule_storage_file_deletion,
)
from .forms import (
    BulkPhotoUploadForm,
    FolderCreateForm,
    PhotoEditForm,
    prepare_uploaded_image_for_storage,
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status
from rest_framework.permissions import AllowAny

from .serializer import PhotoSerializer
# ---------- Helpers ----------

logger = logging.getLogger(__name__)


class PhotoList(APIView):
    """
    GET /api/photos/?label=<slug>&limit=50&offset=0

    - label=<slug> filters by label
    - folder=<slug> remains a temporary query-string alias
    - limit/offset are optional (default 50/0, hard-capped)
    """
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self, request: Request):
        qs = (
            Photo.objects.select_related("label")
            .only(
                "id", "title", "description", "category",
                "created_at", "order",
                "aperture", "iso", "shutter_speed",
                "image", "thumb", "preview", "blur_data_url",
                "label", "label__title", "label__slug", "label__order",
            )
            .order_by("-order", "-id")
        )

        label_slug = request.GET.get("label") or request.GET.get("folder")
        if label_slug:
            qs = qs.filter(label__slug=label_slug)

        return qs

    def paginate(self, request: Request, qs):
        try:
            limit = min(
                max(int(request.GET.get("limit", self.DEFAULT_LIMIT)), 1),
                self.MAX_LIMIT,
            )
        except ValueError:
            limit = self.DEFAULT_LIMIT

        try:
            offset = max(int(request.GET.get("offset", 0)), 0)
        except ValueError:
            offset = 0

        total = qs.count()
        items = list(qs[offset: offset + limit])
        next_offset = offset + limit if offset + limit < total else None
        prev_offset = max(offset - limit, 0) if offset > 0 else None

        return items, {
            "count": total,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
            "prev_offset": prev_offset,
        }

    def get(self, request: Request):
        qs = self.get_queryset(request)
        items, meta = self.paginate(request, qs)
        serializer = PhotoSerializer(items, many=True, context={"request": request})
        response = Response(
            {"results": serializer.data, "meta": meta},
            status=status.HTTP_200_OK,
        )
        patch_cache_control(response, public=True, max_age=60)
        return response

def _normalize_order(label: Label | None):
    """
    Keep contiguous ordering (n..1) inside a label, or among unlabeled photos.
    Uses bulk_update to avoid n queries.
    """
    with transaction.atomic():
        if label:
            qs = Photo.objects.filter(label=label)
        else:
            qs = Photo.objects.filter(label__isnull=True)

        photos = list(qs.order_by("-order").only("id", "order"))
        n = len(photos)
        for i, p in enumerate(photos):
            p.order = n - i
        if photos:
            Photo.objects.bulk_update(photos, ["order"])


def _photo_title_from_upload(upload, title_prefix=""):
    base_name = os.path.splitext(os.path.basename(upload.name))[0]
    title = base_name.replace("_", " ").replace("-", " ").strip().title()
    prefix = title_prefix.strip()
    if not title:
        title = "Untitled"
    if prefix:
        return f"{prefix} - {title}"
    return title


def _next_order_for_label(label: Label | None, exclude_photo_id=None):
    qs = Photo.objects.filter(label=label)
    if exclude_photo_id:
        qs = qs.exclude(id=exclude_photo_id)
    return (qs.aggregate(models.Max("order"))["order__max"] or 0) + 1


def _unique_label_slug(title):
    base_slug = slugify(title) or "folder"
    candidate = base_slug
    suffix = 2
    while Label.objects.filter(slug=candidate).exists():
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


def _manager_context(photos, active_label=None, folder_form=None, **extra):
    labels = Label.objects.annotate(photo_count=models.Count("photos")).order_by(
        "-order", "-id"
    )
    context = {
        "photos": photos,
        "active_label": active_label,
        "labels": labels,
        "total_photo_count": Photo.objects.count(),
        "unfiled_count": Photo.objects.filter(label__isnull=True).count(),
        "folder_form": folder_form or FolderCreateForm(),
    }
    context.update(extra)
    return context


def _manager_redirect(return_label_slug="", return_view=""):
    if return_label_slug and Label.objects.filter(slug=return_label_slug).exists():
        return redirect("label_detail", slug=return_label_slug)
    if return_view == "unfiled":
        return redirect(f'{reverse("photo_list")}?view=unfiled')
    return redirect("photo_list")


# ---------- Public views ----------

def label_list(request):
    """List all labels and the number of unlabeled photos."""
    labels = Label.objects.all().order_by("-order", "-id")
    unlabeled_count = Photo.objects.filter(label__isnull=True).count()
    return render(
        request,
        "photos/label_list.html",
        {"labels": labels, "unlabeled_count": unlabeled_count},
    )


def label_detail(request, slug):
    """Photos assigned to one label."""
    label = get_object_or_404(Label, slug=slug)
    photos = label.photos.all().order_by("-order", "-id")
    return render(
        request,
        "photos/photo_list.html",
        _manager_context(photos, active_label=label),
    )


def photo_list(request):
    """All photos across labels."""
    show_unfiled = request.GET.get("view") == "unfiled"
    photos = Photo.objects.all()
    if show_unfiled:
        photos = photos.filter(label__isnull=True)
    photos = photos.order_by("-order", "-id")
    return render(
        request,
        "photos/photo_list.html",
        _manager_context(photos, show_unfiled=show_unfiled),
    )


# ---------- Admin-only actions ----------

@staff_member_required
def upload_photo(request):
    if request.method == "POST":
        form = BulkPhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            label = form.cleaned_data["label"]
            title_prefix = form.cleaned_data["title_prefix"]
            description = form.cleaned_data["description"]
            images = form.cleaned_data["images"]

            uploaded_photo_ids = []
            failed_names = []
            optimized_count = 0
            for image in images:
                original_name = image.name
                stored_image = image
                camera_settings = {}
                was_optimized = False
                if settings.USE_CLOUDINARY:
                    try:
                        (
                            stored_image,
                            camera_settings,
                            was_optimized,
                        ) = prepare_uploaded_image_for_storage(
                            image,
                            max_bytes=settings.CLOUDINARY_MAX_IMAGE_BYTES,
                            max_pixels=settings.CLOUDINARY_MAX_IMAGE_PIXELS,
                        )
                    except Exception:
                        logger.exception(
                            "Unable to optimize photo %s",
                            original_name,
                        )
                        failed_names.append(original_name)
                        continue

                photo = Photo(
                    title=_photo_title_from_upload(image, title_prefix),
                    description=description,
                    label=label,
                    image=stored_image,
                    **camera_settings,
                )
                photo._defer_derivatives = True
                try:
                    photo.save()
                except Exception:
                    logger.exception("Unable to upload photo %s", original_name)
                    failed_names.append(original_name)
                    if (
                        photo.image
                        and photo.image.name
                        and getattr(photo.image, "_committed", False)
                    ):
                        schedule_storage_file_deletion([photo.image.name])
                else:
                    uploaded_photo_ids.append(photo.pk)
                    optimized_count += int(was_optimized)

            if uploaded_photo_ids:
                _normalize_order(label)
                schedule_photo_derivative_generation(uploaded_photo_ids)
                uploaded_count = len(uploaded_photo_ids)
                messages.success(
                    request,
                    f"Uploaded {uploaded_count} "
                    f"photo{'s' if uploaded_count != 1 else ''}. "
                    "Optimized previews are processing.",
                )
                if optimized_count:
                    messages.info(
                        request,
                        f"Optimized {optimized_count} oversized "
                        f"photo{'s' if optimized_count != 1 else ''} "
                        "for Cloudinary.",
                    )
                if failed_names:
                    failed_summary = ", ".join(failed_names[:3])
                    if len(failed_names) > 3:
                        failed_summary += f" and {len(failed_names) - 3} more"
                    messages.warning(
                        request,
                        f"Could not upload {len(failed_names)} file"
                        f"{'s' if len(failed_names) != 1 else ''}: {failed_summary}.",
                    )
                if label:
                    return redirect("label_detail", slug=label.slug)
                return redirect("photo_list")

            form.add_error(
                "images",
                "No photos were uploaded. Try a smaller batch and check the server log.",
            )
    else:
        form = BulkPhotoUploadForm()
    return render(request, "photos/upload_photo.html", {"form": form})


@staff_member_required
@require_POST
def create_folder(request):
    form = FolderCreateForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            folder = form.save(commit=False)
            folder.slug = _unique_label_slug(folder.title)
            folder.order = (
                Label.objects.aggregate(models.Max("order"))["order__max"] or 0
            ) + 1
            folder.save()

        messages.success(request, f'Created folder "{folder.title}".')
        return redirect("label_detail", slug=folder.slug)

    return_label_slug = request.POST.get("return_label", "")
    return_view = request.POST.get("return_view", "")
    active_label = Label.objects.filter(slug=return_label_slug).first()
    if active_label:
        photos = active_label.photos.all().order_by("-order", "-id")
    elif return_view == "unfiled":
        photos = Photo.objects.filter(label__isnull=True).order_by("-order", "-id")
    else:
        photos = Photo.objects.all().order_by("-order", "-id")
    return render(
        request,
        "photos/photo_list.html",
        _manager_context(
            photos,
            active_label=active_label,
            folder_form=form,
            open_folder_dialog=True,
            show_unfiled=return_view == "unfiled",
        ),
        status=400,
    )


@staff_member_required
@require_POST
def bulk_photos(request):
    return_label_slug = request.POST.get("return_label", "")
    return_view = request.POST.get("return_view", "")
    selected_ids = []
    for value in request.POST.getlist("photo_ids"):
        try:
            selected_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    photos = list(
        Photo.objects.select_related("label").filter(id__in=set(selected_ids))
    )
    if not photos:
        messages.error(request, "Select at least one photo.")
        return _manager_redirect(return_label_slug, return_view)

    action = request.POST.get("action")
    photo_count = len(photos)

    if action == "delete":
        affected_label_ids = {photo.label_id for photo in photos}
        storage_names = [
            field.name
            for photo in photos
            for field in (photo.image, photo.thumb, photo.preview)
            if field and field.name
        ]

        with transaction.atomic():
            for photo in photos:
                photo._defer_storage_cleanup = True
                photo.delete()
            for label_id in affected_label_ids:
                label = Label.objects.filter(id=label_id).first() if label_id else None
                _normalize_order(label)
            transaction.on_commit(
                lambda names=tuple(storage_names): schedule_storage_file_deletion(names)
            )

        messages.success(
            request,
            f"Deleted {photo_count} photo{'s' if photo_count != 1 else ''}.",
        )
        return _manager_redirect(return_label_slug, return_view)

    if action != "edit":
        messages.error(request, "Choose a valid bulk action.")
        return _manager_redirect(return_label_slug, return_view)

    folder_value = request.POST.get("folder", "__keep__")
    replace_description = request.POST.get("replace_description") == "on"
    update_folder = folder_value != "__keep__"

    if not update_folder and not replace_description:
        messages.error(request, "Choose at least one detail to update.")
        return _manager_redirect(return_label_slug, return_view)

    target_label = None
    if update_folder and folder_value != "__none__":
        try:
            target_label = Label.objects.get(id=int(folder_value))
        except (Label.DoesNotExist, TypeError, ValueError):
            messages.error(request, "Choose a valid folder.")
            return _manager_redirect(return_label_slug, return_view)

    changed_fields = []
    affected_label_ids = {photo.label_id for photo in photos}
    if update_folder:
        next_order = _next_order_for_label(target_label)
        for photo in photos:
            photo.label = target_label
            photo.order = next_order
            next_order += 1
        changed_fields.extend(["label", "order"])
        affected_label_ids.add(target_label.id if target_label else None)

    if replace_description:
        description = request.POST.get("description", "")
        for photo in photos:
            photo.description = description
        changed_fields.append("description")

    with transaction.atomic():
        Photo.objects.bulk_update(photos, changed_fields)
        for label_id in affected_label_ids:
            label = Label.objects.filter(id=label_id).first() if label_id else None
            _normalize_order(label)

    messages.success(
        request,
        f"Updated {photo_count} photo{'s' if photo_count != 1 else ''}.",
    )
    return _manager_redirect(return_label_slug, return_view)


@staff_member_required
def edit_photo(request, id):
    photo = get_object_or_404(Photo, id=id)
    previous_label = photo.label

    if request.method == "POST":
        form = PhotoEditForm(request.POST, request.FILES, instance=photo)
        if form.is_valid():
            updated = form.save(commit=False)
            label_changed = previous_label != updated.label
            if label_changed:
                updated.order = _next_order_for_label(updated.label, updated.id)
            updated.save()

            if label_changed:
                _normalize_order(previous_label)
                _normalize_order(updated.label)

            messages.success(request, "Photo updated.")
            return redirect("photo_list")
    else:
        form = PhotoEditForm(instance=photo)

    return render(
        request,
        "photos/edit_photo.html",
        {"form": form, "photo": photo},
    )


@staff_member_required
@require_POST
def remove_label(request, id):
    photo = get_object_or_404(Photo, id=id)
    previous_label = photo.label

    if previous_label:
        photo.label = None
        photo.order = _next_order_for_label(None, photo.id)
        photo.save(update_fields=["label", "order"])
        _normalize_order(previous_label)
        _normalize_order(None)
        messages.success(request, "Photo removed from its folder.")

    return redirect("photo_list")


@staff_member_required
@require_POST
def up_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    prev_photo = (
        Photo.objects.filter(label=photo.label, order__gt=photo.order)
        .order_by("order")
        .first()
    )
    if prev_photo:
        photo.order, prev_photo.order = prev_photo.order, photo.order
        photo.save(update_fields=["order"])
        prev_photo.save(update_fields=["order"])
    _normalize_order(photo.label)
    return redirect("photo_list")


@staff_member_required
@require_POST
def down_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    next_photo = (
        Photo.objects.filter(label=photo.label, order__lt=photo.order)
        .order_by("-order")
        .first()
    )
    if next_photo:
        photo.order, next_photo.order = next_photo.order, photo.order
        photo.save(update_fields=["order"])
        next_photo.save(update_fields=["order"])
    _normalize_order(photo.label)
    return redirect("photo_list")


@staff_member_required
@require_POST
def top_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    max_order = (
        Photo.objects.filter(label=photo.label)
        .aggregate(models.Max("order"))["order__max"]
        or 0
    )
    photo.order = max_order + 1
    photo.save(update_fields=["order"])
    _normalize_order(photo.label)
    return redirect("photo_list")


@staff_member_required
@require_POST
def bottom_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    min_order = (
        Photo.objects.filter(label=photo.label)
        .aggregate(models.Min("order"))["order__min"]
        or 0
    )
    photo.order = min_order - 1
    photo.save(update_fields=["order"])
    _normalize_order(photo.label)
    return redirect("photo_list")


@staff_member_required
@require_POST
def delete_photo(request, id):
    photo = get_object_or_404(Photo, id=id)
    label = photo.label
    photo.delete()  # S3 file removed via post_delete signal in models.py
    _normalize_order(label)
    return redirect("photo_list")
