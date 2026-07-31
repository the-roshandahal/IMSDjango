from django.urls import path

from apps.reports import web_views

app_name = "reports_web"

urlpatterns = [
    path("reports/", web_views.ReportHubView.as_view(), name="hub"),
    path("reports/inventory/", web_views.InventoryReportView.as_view(), name="inventory"),
    path("reports/consumption/", web_views.ConsumptionReportView.as_view(), name="consumption"),
    path("reports/equipment/", web_views.EquipmentReportView.as_view(), name="equipment"),
    path("reports/projects/", web_views.ProjectReportView.as_view(), name="projects"),
    path("reports/purchasing/", web_views.PurchasingReportView.as_view(), name="purchasing"),
    path("reports/vehicles/", web_views.VehicleReportView.as_view(), name="vehicles"),
    path("reports/audit/", web_views.AuditReportView.as_view(), name="audit"),
]
