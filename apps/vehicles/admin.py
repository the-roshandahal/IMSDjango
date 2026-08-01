from django.contrib import admin

from apps.vehicles.models import Vehicle, VehicleCostLog, VehicleLog


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration", "status", "current_location", "assigned_driver", "service_due_date", "insurance_expiry")
    list_filter = ("status",)
    search_fields = ("registration", "make_model")


@admin.register(VehicleLog)
class VehicleLogAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "action", "location", "driver", "performed_by", "timestamp")
    list_filter = ("action",)
    readonly_fields = [f.name for f in VehicleLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(VehicleCostLog)
class VehicleCostLogAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "cost_type", "amount", "incurred_at", "location", "recorded_by")
    list_filter = ("cost_type",)
