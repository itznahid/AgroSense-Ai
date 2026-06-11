"""CropReco/urls.py — AgroSense Enterprise URL Configuration"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", include("accounts.urls")),
    path("marketplace/", include("marketplace.urls")),
    path("recommend/", include("recommend.urls")),
    path("disease/", include("crop_disease.urls")),
    path("chat/", include("chatbot.urls")),
    path("ai-admin/", include("ai_admin.urls", namespace="ai_admin")),
    path("orders/", include("orders.urls")),

    # PWA
    path("", include("pwa.urls")),
]

if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)