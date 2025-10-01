# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST

from .models import Photo, Folder
from .forms import PhotoForm

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status


from .serializer import PhotoSerializer


# ---------- API ----------

class PhotoList(APIView):
    """
    GET /api/photos/?folder=<slug>&limit=50&offset=0

    - folder=<slug> filters to a folder by slug
    - limit/offset are optional (default 50/0, hard-capped)
    """
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200

    def get_queryset(self, request: Request):
        qs = (
            Photo.objects.select_related("folder")
            .only(
                "id", "title", "description", "category",
                "created_at", "order",
                "image", "thumb", "preview", "blur_data_url",
                "folder",  # FK id for select_related
            )
            .order_by("-order", "-id")
        )

        folder_slug = request.GET.get("folder")
        if folder_slug:
            qs = qs.filter(folder__slug=folder_slug)

        return qs

    def paginate(self, request: Request, qs):
        try:
            limit = min(int(request.GET.get("limit", self.DEFAULT_LIMIT)), self.MAX_LIMIT)
        except ValueError:
            limit = self.DEFAULT_LIMIT

        try:
            offset = int(request.GET.get("offset", 0))
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
        return Response({"results": serializer.data, "meta": meta}, status=status.HTTP_200_OK)
