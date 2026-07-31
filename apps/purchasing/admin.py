from django.contrib import admin

from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "supplier", "warehouse", "status", "expected_date", "created_at"]
    list_filter = ["status"]
    search_fields = ["reference", "supplier__name"]
    inlines = [PurchaseOrderLineInline]
