from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST

from .models import Photo
from .forms import PhotoForm

from rest_framework.views import APIView
from rest_framework.response import Response
from .serializer import PhotoSerializer


# Public gallery
def photo_list(request):
    photos = Photo.objects.all().order_by('-order')
    return render(request, 'photos/photo_list.html', {'photos': photos})


# Admin-only upload page
@staff_member_required
def upload_photo(request):
    if request.method == 'POST':
        form = PhotoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()  # with S3 storage configured, this uploads to S3
            return redirect('photo_list')
    else:
        form = PhotoForm()
    return render(request, 'photos/upload_photo.html', {'form': form})


# Keep orders contiguous (bulk update to avoid N queries)
def normalize_order():
    with transaction.atomic():
        photos = list(Photo.objects.order_by('-order').only('id', 'order'))
        n = len(photos)
        for i, p in enumerate(photos):
            p.order = n - i
        if photos:
            Photo.objects.bulk_update(photos, ['order'])


@staff_member_required
@require_POST
def up_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    prev_photo = (
        Photo.objects.filter(order__gt=photo.order)
        .order_by('order')
        .first()
    )
    if prev_photo:
        photo.order, prev_photo.order = prev_photo.order, photo.order
        photo.save(update_fields=['order'])
        prev_photo.save(update_fields=['order'])
    normalize_order()
    return redirect('photo_list')


@staff_member_required
@require_POST
def down_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    next_photo = (
        Photo.objects.filter(order__lt=photo.order)
        .order_by('-order')
        .first()
    )
    if next_photo:
        photo.order, next_photo.order = next_photo.order, photo.order
        photo.save(update_fields=['order'])
        next_photo.save(update_fields=['order'])
    normalize_order()
    return redirect('photo_list')


@staff_member_required
@require_POST
def top_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    max_order = Photo.objects.aggregate(models.Max('order'))['order__max'] or 0
    photo.order = max_order + 1
    photo.save(update_fields=['order'])
    normalize_order()
    return redirect('photo_list')


@staff_member_required
@require_POST
def bottom_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    min_order = Photo.objects.aggregate(models.Min('order'))['order__min'] or 0
    photo.order = min_order - 1
    photo.save(update_fields=['order'])
    normalize_order()
    return redirect('photo_list')


@staff_member_required
@require_POST
def delete_photo(request, id):
    photo = get_object_or_404(Photo, id=id)
    photo.delete()          # make sure you have a post_delete signal to remove S3 file
    normalize_order()
    return redirect('photo_list')


class PhotoList(APIView):
    def get(self, request):
        photos = Photo.objects.all().order_by('-order')
        serializer = PhotoSerializer(photos, many=True, context={"request": request})
        return Response(serializer.data)
