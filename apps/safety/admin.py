from django.contrib import admin

from apps.safety.models import HazardReport


@admin.register(HazardReport)
class HazardReportAdmin(admin.ModelAdmin):
    list_display = ["title", "report_type", "severity", "status", "site", "reported_by", "reported_at"]
    list_filter = ["report_type", "severity", "status"]
    search_fields = ["title", "description"]
