from django.contrib import admin

from apps.requests.models import StockRequest, StockRequestLine


class StockRequestLineInline(admin.TabularInline):
    model = StockRequestLine
    extra = 0


@admin.register(StockRequest)
class StockRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "station", "warehouse", "requested_by", "status", "requested_at", "decided_at")
    list_filter = ("status", "warehouse", "station")
    inlines = [StockRequestLineInline]
