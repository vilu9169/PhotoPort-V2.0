from django.shortcuts import render, redirect, get_object_or_404
from .models import Photo
from .forms import PhotoForm
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializer import PhotoSerializer
from django.db import models

# Create your views here.
def photo_list(request):
    photos = Photo.objects.all().order_by('-order')
    return render(request, 'photos/photo_list.html', {'photos': photos})

def upload_photo(request):
    if request.method == 'POST':
        form = PhotoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('photo_list')
    else:
        form = PhotoForm()
    return render(request, 'photos/upload_photo.html', {'form': form})

def normalize_order():
    photos = Photo.objects.order_by('-order')
    for index, photo in enumerate(photos):
        photo.order = len(photos) - index
        photo.save()

def up_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    # Find the previous photo (one with a lower order)
    previous_photo = Photo.objects.filter(order__gt=photo.order).order_by('order').first()
    if previous_photo:
        # Swap the order values
        photo.order, previous_photo.order = previous_photo.order, photo.order
        photo.save()
        previous_photo.save()
    normalize_order()
    return redirect('photo_list')

def down_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    # Find the next photo (one with a higher order)
    next_photo = Photo.objects.filter(order__lt=photo.order).order_by('-order').first()
    if next_photo:
        # Swap the order values
        photo.order, next_photo.order = next_photo.order, photo.order
        photo.save()
        next_photo.save()
    normalize_order()
    return redirect('photo_list')

def top_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    max_order = Photo.objects.aggregate(models.Max('order'))['order__max']
    photo.order = (max_order or 0) + 1
    photo.save()
    normalize_order()
    return redirect('photo_list')

def bottom_order(request, id):
    photo = get_object_or_404(Photo, id=id)
    min_order = Photo.objects.aggregate(models.Min('order'))['order__min']
    photo.order = (min_order or 0) - 1
    photo.save()
    normalize_order()
    return redirect('photo_list')


class PhotoList(APIView):
    def get(self, request):
        photos = Photo.objects.all()
        serializer = PhotoSerializer(photos, many=True)
        print(serializer.data)
        return Response(serializer.data)