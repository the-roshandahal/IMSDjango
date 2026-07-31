from django.urls import path

from apps.audit.views import AuditLogListView

app_name = "audit"

urlpatterns = [
    path("audit/", AuditLogListView.as_view(), name="log"),
]
