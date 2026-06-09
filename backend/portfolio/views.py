from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_POST

from .models import Label, Photo
from .forms import PhotoForm

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status
from rest_framework.permissions import AllowAny

from .serializer import PhotoSerializer
# ---------- Helpers ----------

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
        {"photos": photos, "active_label": label},
    )


def photo_list(request):
    """All photos across labels."""
    photos = Photo.objects.all().order_by("-order", "-id")
    return render(
        request,
        "photos/photo_list.html",
        {"photos": photos, "active_label": None},
    )


# ---------- Admin-only actions ----------

@staff_member_required
def upload_photo(request):
    if request.method == "POST":
        form = PhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save()  # goes to S3 if configured
            _normalize_order(photo.label)
            if photo.label:
                return redirect("label_detail", slug=photo.label.slug)
            return redirect("photo_list")
    else:
        form = PhotoForm()
    return render(request, "photos/upload_photo.html", {"form": form})


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
