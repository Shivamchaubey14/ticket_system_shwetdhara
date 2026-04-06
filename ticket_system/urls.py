from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.urls import path,include
from django.views.static import serve
from django.contrib import admin
from main_app_ticket.admin import ksts_admin
urlpatterns = [
    path('admin/', ksts_admin.urls),
    path('',include('main_app_ticket.urls')),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)