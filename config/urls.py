from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("api/", include("apps.catalogue.urls")),
    path("api/", include("apps.warehouses.urls")),
    path("api/", include("apps.inventory.urls")),
    path("api/", include("apps.requests.urls")),
    path("api/", include("apps.equipment.urls")),
    path("api/", include("apps.vehicles.urls")),
    path("", include("apps.catalogue.urls_web")),
    path("", include("apps.warehouses.urls_web")),
    path("", include("apps.inventory.urls_web")),
    path("", include("apps.requests.urls_web")),
    path("", include("apps.audit.urls")),
    path("", include("apps.equipment.urls_web")),
    path("", include("apps.vehicles.urls_web")),
    path("", include("apps.projects.urls_web")),
    path("", include("apps.suppliers.urls_web")),
    path("", include("apps.purchasing.urls_web")),
    path("", include("apps.reports.urls_web")),
    path("", include("apps.notifications.urls_web")),
    path("", include("apps.documents.urls_web")),
    path("", include("apps.core.urls_web")),
    path("", include("apps.trains.urls_web")),
    path("", include("apps.employees.urls_web")),
    path("", include("apps.safety.urls_web")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "apps.core.error_views.error_400"
handler403 = "apps.core.error_views.error_403"
handler404 = "apps.core.error_views.error_404"
handler500 = "apps.core.error_views.error_500"
