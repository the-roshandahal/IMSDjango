from django.contrib import admin

from apps.inventory.models import InventoryTransaction, StockLevel, Stocktake, StocktakeLine, Transfer


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "type", "product", "quantity", "source_warehouse", "dest_warehouse", "station", "performed_by")
    list_filter = ("type", "source_warehouse", "dest_warehouse", "station")
    search_fields = ("product__name", "reason_code")
    readonly_fields = [f.name for f in InventoryTransaction._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "station", "batch", "quantity")
    list_filter = ("warehouse", "station")
    search_fields = ("product__name",)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "source_warehouse", "dest_warehouse", "dest_station", "status")
    list_filter = ("status",)


@admin.register(Stocktake)
class StocktakeAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "started_by", "started_at", "status")


admin.site.register(StocktakeLine)
