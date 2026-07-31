from django.contrib import admin

from apps.suppliers.models import Supplier, SupplierProduct


class SupplierProductInline(admin.TabularInline):
    model = SupplierProduct
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "contact_person", "phone", "email", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "contact_person", "email"]
    inlines = [SupplierProductInline]


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ["supplier", "product", "unit_price", "is_preferred", "updated_at"]
    list_filter = ["is_preferred"]
