from django.contrib import admin

from apps.projects.models import DeepCleanProject, ShiftLog


@admin.register(DeepCleanProject)
class DeepCleanProjectAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "location", "supervisor", "status", "start_date", "end_date")
    list_filter = ("status",)
    search_fields = ("reference", "name")


@admin.register(ShiftLog)
class ShiftLogAdmin(admin.ModelAdmin):
    list_display = ("project", "work_date", "shift", "start_time", "end_time", "logged_by")
    list_filter = ("shift",)
