from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST

from .models import Photo, Folder
from .forms import PhotoForm  # Make sure the form includes a `folder` field

from rest_framework.views import APIView
from rest_framework.response import Response
from .serializer import PhotoSerializer


# ---------- Helpers ----------

def _normalize_order(folder: Folder | None):
    """
    Keep contiguous ordering (n..1) inside a folder, or among ungrouped photos.
    Uses bulk_update to avoid n queries.
    """
    with transaction.atomic():
        if folder:
            qs = Photo.objects.filter(folder=folder)
        else:
            qs = Photo.objects.filter(folder__isnull=True)

        photos = list(qs.order_by("-order").only("id", "order"))
        n = len(photos)
        for i, p in enumerate(photos):
            p.order = n - i
        if photos:
            Photo.objects.bulk_update(photos, ["order"])


# ---------- Public views ----------

def folder_list(request):
    """List all folders (and show count of ungrouped photos)."""
    folders = Folder.objects.all().order_by("-order", "-id")
    ungrouped_count = Photo.objects.filter(folder__isnull=True).count()
    return render(
        request,
        "photos/folder_list.html",
        {"folders": folders, "ungrouped_count": ungrouped_count},
    )


def folder_detail(request, slug):
    """Photos inside one folder."""
    folder = get_object_or_404(Folder, slug=slug)
    photos = folder.photos.all().order_by("-order", "-id")
    return render(
        request,
        "photos/photo_list.html",
        {"photos": photos, "active_folder": folder},
    )


def photo_list(request):
    """All photos (across folders). If you prefer 'ungrouped only', filter here."""
    photos = Photo.objects.all().order_by("-order", "-id")
    return render(
        request,
        "photos/photo_list.html",
        {"photos": photos, "active_folder": None},
    )


# ---------- Admin-only actions ----------

@staff_member_required
def upload_photo(request):
    if request.method == "POST":
        form = PhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save()  # goes to S3 if configured
            _normalize_order(photo.folder)
            # Optional: redirect to that folder's page if set
            if photo.folder:
                return redirect("folder_detail", slug=photo.folder.slug)
            return redirect("photo_list")
    else:
        form = PhotoForm()
    return render(request, "photos/upload_photo.html", {"form": form})


@staff_member_required
@require_POST
def up_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    prev_photo = (
        Photo.objects.filter(folder=photo.folder, order__gt=photo.order)
        .order_by("order")
        .first()
    )
    if prev_photo:
        photo.order, prev_photo.order = prev_photo.order, photo.order
        photo.save(update_fields=["order"])
        prev_photo.save(update_fields=["order"])
    _normalize_order(photo.folder)
    return redirect("photo_list")


@staff_member_required
@require_POST
def down_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    next_photo = (
        Photo.objects.filter(folder=photo.folder, order__lt=photo.order)
        .order_by("-order")
        .first()
    )
    if next_photo:
        photo.order, next_photo.order = next_photo.order, photo.order
        photo.save(update_fields=["order"])
        next_photo.save(update_fields=["order"])
    _normalize_order(photo.folder)
    return redirect("photo_list")


@staff_member_required
@require_POST
def top_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    max_order = (
        Photo.objects.filter(folder=photo.folder)
        .aggregate(models.Max("order"))["order__max"]
        or 0
    )
    photo.order = max_order + 1
    photo.save(update_fields=["order"])
    _normalize_order(photo.folder)
    return redirect("photo_list")


@staff_member_required
@require_POST
def bottom_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    min_order = (
        Photo.objects.filter(folder=photo.folder)
        .aggregate(models.Min("order"))["order__min"]
        or 0
    )
    photo.order = min_order - 1
    photo.save(update_fields=["order"])
    _normalize_order(photo.folder)
    return redirect("photo_list")


@staff_member_required
@require_POST
def delete_photo(request, id):
    photo = get_object_or_404(Photo, id=id)
    folder = photo.folder
    photo.delete()  # S3 file removed via post_delete signal in models.py
    _normalize_order(folder)
    return redirect("photo_list")


# ---------- API ----------

class PhotoList(APIView):
    def get(self, request):
        """
        GET /api/photos/?folder=<slug>  -> filter by folder
        """
        qs = Photo.objects.all().order_by("-order", "-id")
        folder_slug = request.GET.get("folder")
        if folder_slug:
            qs = qs.filter(folder__slug=folder_slug)
        serializer = PhotoSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)
