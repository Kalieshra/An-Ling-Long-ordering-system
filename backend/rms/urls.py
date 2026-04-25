from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls_api")),
    path("api/v1/menu/", include("menu.urls_api")),
    path("dashboard/menu/", include("menu.urls_dashboard")),
    path("", include("accounts.urls_web")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
