from django.urls import path

from apps.warehouses import web_views

app_name = "warehouses_web"

urlpatterns = [
    path("warehouses/", web_views.WarehouseListView.as_view(), name="warehouse-list"),
    path("warehouses/create/", web_views.WarehouseCreateView.as_view(), name="warehouse-create"),
    path("warehouses/<int:pk>/", web_views.WarehouseDetailView.as_view(), name="warehouse-detail"),
    path("warehouses/<int:pk>/edit/", web_views.WarehouseUpdateView.as_view(), name="warehouse-edit"),
    path("stations/", web_views.StationListView.as_view(), name="station-list"),
    path("stations/create/", web_views.StationCreateView.as_view(), name="station-create"),
    path("stations/<int:pk>/", web_views.StationDetailView.as_view(), name="station-detail"),
    path("stations/<int:pk>/edit/", web_views.StationUpdateView.as_view(), name="station-edit"),
]
