from django.urls import path

from apps.equipment import web_views

app_name = "equipment_web"

urlpatterns = [
    path("equipment/", web_views.EquipmentListView.as_view(), name="list"),
    path("equipment/create/", web_views.EquipmentCreateView.as_view(), name="create"),
    path("equipment/<int:pk>/", web_views.EquipmentDetailView.as_view(), name="detail"),
    path("equipment/<int:pk>/edit/", web_views.EquipmentUpdateView.as_view(), name="edit"),
    path("equipment/<int:pk>/assign/", web_views.EquipmentAssignView.as_view(), name="assign"),
    path("equipment/<int:pk>/release/", web_views.EquipmentReleaseView.as_view(), name="release"),
    path("equipment/<int:pk>/maintenance/start/", web_views.EquipmentMaintenanceStartView.as_view(), name="maintenance-start"),
    path("equipment/<int:pk>/maintenance/end/", web_views.EquipmentMaintenanceEndView.as_view(), name="maintenance-end"),
    path("equipment/<int:pk>/test/", web_views.EquipmentTestView.as_view(), name="test"),
    path("equipment/<int:pk>/lost/", web_views.EquipmentLostView.as_view(), name="lost"),
    path("equipment/<int:pk>/write-off/", web_views.EquipmentWriteOffView.as_view(), name="write-off"),
]
