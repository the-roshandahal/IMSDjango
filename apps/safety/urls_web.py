from django.urls import path

from apps.safety import web_views

app_name = "safety_web"

urlpatterns = [
    path("hazards/", web_views.HazardReportListView.as_view(), name="list"),
    path("hazards/new/", web_views.HazardReportCreateView.as_view(), name="new"),
    path("hazards/<int:pk>/", web_views.HazardReportDetailView.as_view(), name="detail"),
    path("hazards/<int:pk>/resolve/", web_views.HazardReportResolveView.as_view(), name="resolve"),
]
