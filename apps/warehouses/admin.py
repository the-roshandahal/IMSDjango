from django.contrib import admin

from apps.warehouses.models import Station, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "is_active")
    search_fields = ("name",)


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
