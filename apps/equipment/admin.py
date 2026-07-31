from django.contrib import admin

from apps.equipment.models import Equipment, EquipmentLog


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("asset_id", "name", "status", "current_station", "assigned_user", "next_maintenance_due", "last_test_result")
    list_filter = ("status", "last_test_result")
    search_fields = ("asset_id", "name", "serial_number")


@admin.register(EquipmentLog)
class EquipmentLogAdmin(admin.ModelAdmin):
    list_display = ("equipment", "action", "station", "assigned_user", "performed_by", "timestamp")
    list_filter = ("action",)
    readonly_fields = [f.name for f in EquipmentLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
