from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("accounts.urls_api")),
    path("api/v1/me/", include("accounts.urls_me")),
    path("api/v1/menu/", include("menu.urls_api")),
    path("api/v1/orders/", include("orders.urls_api")),
    path("dashboard/menu/", include("menu.urls_dashboard")),
    path("cashier/", include("orders.urls_cashier")),
    path("kitchen/", include("orders.urls_kitchen")),
    path("", include("accounts.urls_web")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
