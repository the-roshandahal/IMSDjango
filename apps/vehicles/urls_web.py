from django.urls import path

from apps.vehicles import web_views

app_name = "vehicles_web"

urlpatterns = [
    path("vehicles/", web_views.VehicleListView.as_view(), name="list"),
    path("vehicles/create/", web_views.VehicleCreateView.as_view(), name="create"),
    path("vehicles/<int:pk>/", web_views.VehicleDetailView.as_view(), name="detail"),
    path("vehicles/<int:pk>/edit/", web_views.VehicleUpdateView.as_view(), name="edit"),
    path("vehicles/<int:pk>/assign/", web_views.VehicleAssignView.as_view(), name="assign"),
    path("vehicles/<int:pk>/release/", web_views.VehicleReleaseView.as_view(), name="release"),
    path("vehicles/<int:pk>/maintenance/start/", web_views.VehicleMaintenanceStartView.as_view(), name="maintenance-start"),
    path("vehicles/<int:pk>/maintenance/end/", web_views.VehicleMaintenanceEndView.as_view(), name="maintenance-end"),
    path("vehicles/<int:pk>/write-off/", web_views.VehicleWriteOffView.as_view(), name="write-off"),
    path("vehicles/<int:pk>/cost-log/", web_views.VehicleCostLogView.as_view(), name="cost-log"),
]
