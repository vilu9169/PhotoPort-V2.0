from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views
from django.contrib.admin.views.decorators import staff_member_required

urlpatterns = [
    path('', staff_member_required(views.photo_list), name='photo_list'),

    path('upload/', staff_member_required(views.upload_photo), name='upload_photo'),
    path('up_order/<int:id>/', staff_member_required(views.up_order), name='up'),
    path('down_order/<int:id>/', staff_member_required(views.down_order), name='down'),
    path('top_order/<int:id>/', staff_member_required(views.top_order), name='top'),
    path('bottom_order/<int:id>/', staff_member_required(views.bottom_order), name='bottom'),

    path('api/photos/', views.PhotoList.as_view(), name='photo_list_api'),
]

# Only serve local files if DEBUG=True

if settings.DEBUG and settings.MEDIA_URL.startswith("/"):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
