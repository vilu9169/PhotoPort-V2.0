# app-level urls.py
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.photo_list, name='photo_list'),
    path('upload/', views.upload_photo, name='upload_photo'),
    path('api/photos/', views.PhotoList.as_view(), name='photo_list_api'),
    path('up_order/<int:id>/', views.up_order, name='up'),
    path('down_order/<int:id>/', views.down_order, name='down'),
    path('top_order/<int:id>/', views.top_order, name='top'),
    path('bottom_order/<int:id>/', views.bottom_order, name='bottom'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
