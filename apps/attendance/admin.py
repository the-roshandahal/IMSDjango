from django.contrib import admin

from apps.attendance.models import ClockEvent, DutySheet, DutySheetAssignment, DutySheetTask, TaskCompletion


class DutySheetTaskInline(admin.TabularInline):
    model = DutySheetTask
    extra = 0


@admin.register(DutySheet)
class DutySheetAdmin(admin.ModelAdmin):
    list_display = ["station", "name", "start_time", "end_time", "is_active"]
    list_filter = ["is_active", "station"]
    search_fields = ["name", "station__name"]
    inlines = [DutySheetTaskInline]


@admin.register(DutySheetAssignment)
class DutySheetAssignmentAdmin(admin.ModelAdmin):
    list_display = ["duty_sheet", "date", "employee", "assigned_by"]
    list_filter = ["date"]
    search_fields = ["employee__first_name", "employee__last_name"]


@admin.register(TaskCompletion)
class TaskCompletionAdmin(admin.ModelAdmin):
    list_display = ["task", "date", "is_completed", "completed_by", "completed_at"]
    list_filter = ["date", "is_completed"]
    search_fields = ["task__description"]


@admin.register(ClockEvent)
class ClockEventAdmin(admin.ModelAdmin):
    list_display = ["employee", "station", "duty_sheet", "clock_in_at", "clock_out_at", "clock_in_method"]
    list_filter = ["station", "clock_in_method"]
    search_fields = ["employee__first_name", "employee__last_name"]
