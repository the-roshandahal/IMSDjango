from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids
from apps.warehouses.forms import StationForm, WarehouseForm
from apps.warehouses.models import Station, Warehouse


class SiteIsObjectQuerysetMixin:
    """For Warehouse/Station, the object itself *is* the site (no FK to
    filter through) -- so scoping is done here instead of via
    SiteScopedQuerysetMixin, matching the pattern in the DRF viewsets."""

    site_type = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in SITE_SCOPE_EXEMPT_ROLES:
            return qs
        return qs.filter(pk__in=list(assigned_site_ids(user, self.site_type)))


def _attach_low_stock_counts(sites, site_field):
    """Sets .low_stock_count on each Warehouse/Station in `sites`, respecting
    any ProductStockThreshold override for that exact site -- a plain
    Product.reorder_point-only DB annotation can't account for those
    per-location overrides, so this resolves it in Python instead, in a
    bounded number of queries regardless of list size."""
    from apps.inventory.models import ProductStockThreshold, StockLevel

    sites = list(sites)
    site_ids = [s.pk for s in sites]
    levels = StockLevel.objects.filter(**{f"{site_field}_id__in": site_ids}).values(
        "product_id", site_field, "quantity", "product__reorder_point"
    )
    overrides = {
        (t.product_id, getattr(t, f"{site_field}_id")): t.reorder_point
        for t in ProductStockThreshold.objects.filter(**{f"{site_field}_id__in": site_ids})
    }
    counts = {}
    for row in levels:
        threshold = overrides.get((row["product_id"], row[site_field]), row["product__reorder_point"])
        if row["quantity"] <= threshold:
            site_id = row[site_field]
            counts[site_id] = counts.get(site_id, 0) + 1
    for s in sites:
        s.low_stock_count = counts.get(s.pk, 0)
    return sites


class WarehouseListView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, ListView):
    capability = "warehouse.view"
    site_type = "warehouse"
    model = Warehouse
    template_name = "warehouses/warehouse_list.html"
    context_object_name = "warehouses"

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).order_by("name")
        return _attach_low_stock_counts(qs, "warehouse")


class WarehouseDetailView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, DetailView):
    capability = "warehouse.view"
    site_type = "warehouse"
    model = Warehouse
    template_name = "warehouses/warehouse_detail.html"
    context_object_name = "warehouse"

    def get_context_data(self, **kwargs):
        from apps.core.permissions import has_capability
        from apps.inventory.models import StockLevel
        from apps.inventory.services import bulk_effective_reorder_points

        ctx = super().get_context_data(**kwargs)
        # quantity>0, plus genuinely out-of-stock lines for actively-managed
        # products (reorder_point set) -- surfaces real stockouts without
        # dredging up every zero-quantity artifact a warehouse ever touched.
        stock = list(
            StockLevel.objects.filter(warehouse=self.object)
            .filter(Q(quantity__gt=0) | Q(quantity__lte=0, product__reorder_point__gt=0))
            .select_related("product", "batch")
            .order_by("product__name")
        )
        thresholds = bulk_effective_reorder_points(stock)
        for sl in stock:
            sl.effective_reorder_point = thresholds[sl.pk]
        ctx["stock"] = stock
        ctx["can_manage_thresholds"] = has_capability(self.request.user, "warehouse.manage")
        return ctx


class WarehouseCreateView(CapabilityRequiredMixin, CreateView):
    capability = "warehouse.manage"
    model = Warehouse
    form_class = WarehouseForm
    template_name = "warehouses/warehouse_form.html"

    def get_success_url(self):
        return reverse("warehouses_web:warehouse-detail", args=[self.object.pk])


class WarehouseUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "warehouse.manage"
    model = Warehouse
    form_class = WarehouseForm
    template_name = "warehouses/warehouse_form.html"

    def get_success_url(self):
        return reverse("warehouses_web:warehouse-detail", args=[self.object.pk])


class StationListView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, ListView):
    capability = "product.view"
    site_type = "station"
    model = Station
    template_name = "warehouses/station_list.html"
    context_object_name = "stations"

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).order_by("name")
        return _attach_low_stock_counts(qs, "station")


class StationDetailView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, DetailView):
    capability = "product.view"
    site_type = "station"
    model = Station
    template_name = "warehouses/station_detail.html"
    context_object_name = "station"

    def get_context_data(self, **kwargs):
        from apps.inventory.models import InventoryTransaction, StockLevel, TransactionType
        from apps.inventory.services import bulk_effective_reorder_points

        ctx = super().get_context_data(**kwargs)
        stock = list(
            StockLevel.objects.filter(station=self.object)
            .filter(Q(quantity__gt=0) | Q(quantity__lte=0, product__reorder_point__gt=0))
            .select_related("product", "batch")
            .order_by("product__name")
        )
        thresholds = bulk_effective_reorder_points(stock)
        for sl in stock:
            sl.effective_reorder_point = thresholds[sl.pk]
        ctx["stock"] = stock
        now = timezone.now()
        ctx["consumption_summary"] = (
            InventoryTransaction.objects.filter(
                station=self.object, type=TransactionType.STATION_USAGE,
                timestamp__year=now.year, timestamp__month=now.month,
            )
            .values("product__name")
            .annotate(total=Sum("quantity"))
            .order_by("-total")
        )
        ctx["recent_requests"] = self.object.stock_requests.select_related("warehouse").order_by("-requested_at")[:5]

        from apps.core.permissions import has_capability
        from apps.inventory.models import Stocktake
        from apps.safety.models import HazardReport

        ctx["recent_stocktakes"] = Stocktake.objects.filter(station=self.object).select_related("started_by")[:5]
        ctx["recent_transactions"] = (
            InventoryTransaction.objects.filter(station=self.object)
            .select_related("product", "source_warehouse", "performed_by")
            .order_by("-timestamp")[:10]
        )
        ctx["can_report_hazards"] = has_capability(self.request.user, "hazard.report") or has_capability(
            self.request.user, "hazard.view"
        )
        ctx["recent_hazards"] = HazardReport.objects.filter(station=self.object).select_related("reported_by")[:5]
        ctx["can_manage_thresholds"] = has_capability(self.request.user, "warehouse.manage")
        return ctx


class StationCreateView(CapabilityRequiredMixin, CreateView):
    capability = "warehouse.manage"
    model = Station
    form_class = StationForm
    template_name = "warehouses/station_form.html"

    def get_success_url(self):
        return reverse("warehouses_web:station-detail", args=[self.object.pk])


class StationUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "warehouse.manage"
    model = Station
    form_class = StationForm
    template_name = "warehouses/station_form.html"

    def get_success_url(self):
        return reverse("warehouses_web:station-detail", args=[self.object.pk])
