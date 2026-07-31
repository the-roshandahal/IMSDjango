from django.contrib import admin

from apps.catalogue.models import Batch, Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "barcode", "is_hazardous", "is_batch_tracked", "is_archived")
    list_filter = ("category", "is_hazardous", "is_batch_tracked", "is_archived")
    search_fields = ("name", "barcode", "qr_code_data")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "batch_number", "expiry_date", "is_expired")
    list_filter = ("warehouse",)
    search_fields = ("batch_number", "product__name")
