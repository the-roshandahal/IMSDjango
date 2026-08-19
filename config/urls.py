from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_media

from apps.core import web_views as core_web_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Unprefixed on purpose: a service worker's default scope is the
    # directory it's served from, so /static/sw.js would only ever be
    # able to control /static/*. Serving it from the root gives it the
    # whole site.
    path("sw.js", core_web_views.ServiceWorkerView.as_view(), name="service-worker"),
    path("manifest.json", core_web_views.ManifestView.as_view(), name="manifest"),
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
    path("", include("apps.attendance.urls_web")),
    path("", include("apps.announcements.urls_web")),
]

# Always serve /media/, not just under DEBUG -- on shared cPanel hosting
# there's no separate web-server config to point at MEDIA_ROOT directly
# (unlike a VPS with real Apache/Nginx vhost access), so Django has to be
# the one serving these files in production too, the same way whitenoise
# already serves collected static files here. Fine for this app's traffic
# level; revisit if that ever changes.
#
# NOTE: django.conf.urls.static.static() looks like it does this but
# actually no-ops (registers zero URL patterns) whenever DEBUG=False --
# it's documented as dev-only. Wiring django.views.static.serve directly
# is what actually makes this unconditional.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_media, {"document_root": settings.MEDIA_ROOT}),
]

handler400 = "apps.core.error_views.error_400"
handler403 = "apps.core.error_views.error_403"
handler404 = "apps.core.error_views.error_404"
handler500 = "apps.core.error_views.error_500"
