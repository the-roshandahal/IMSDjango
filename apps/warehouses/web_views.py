from django.db.models import Sum
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


class WarehouseListView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, ListView):
    capability = "product.view"
    site_type = "warehouse"
    model = Warehouse
    template_name = "warehouses/warehouse_list.html"
    context_object_name = "warehouses"

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).order_by("name")


class WarehouseDetailView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, DetailView):
    capability = "product.view"
    site_type = "warehouse"
    model = Warehouse
    template_name = "warehouses/warehouse_detail.html"
    context_object_name = "warehouse"

    def get_context_data(self, **kwargs):
        from apps.inventory.models import StockLevel

        ctx = super().get_context_data(**kwargs)
        ctx["stock"] = (
            StockLevel.objects.filter(warehouse=self.object, quantity__gt=0)
            .select_related("product", "batch")
            .order_by("product__name")
        )
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
        return super().get_queryset().filter(is_active=True).order_by("name")


class StationDetailView(CapabilityRequiredMixin, SiteIsObjectQuerysetMixin, DetailView):
    capability = "product.view"
    site_type = "station"
    model = Station
    template_name = "warehouses/station_detail.html"
    context_object_name = "station"

    def get_context_data(self, **kwargs):
        from apps.inventory.models import InventoryTransaction, StockLevel, TransactionType

        ctx = super().get_context_data(**kwargs)
        ctx["stock"] = (
            StockLevel.objects.filter(station=self.object, quantity__gt=0)
            .select_related("product", "batch")
            .order_by("product__name")
        )
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
