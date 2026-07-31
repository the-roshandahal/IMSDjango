from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, ensure_site_access
from apps.requests import services
from apps.requests.forms import StockRequestLineFormSet, StockRequestRejectForm, StockRequestWarehouseForm
from apps.requests.models import StockRequest
from apps.requests.services import RequestNotApprovedError
from apps.warehouses.models import Station


class StockRequestListView(CapabilityRequiredMixin, ListView):
    capability = "station_request.view"
    model = StockRequest
    template_name = "requests/stock_request_list.html"
    context_object_name = "stock_requests"
    paginate_by = 30

    def get_queryset(self):
        qs = StockRequest.objects.select_related("station", "warehouse", "requested_by").order_by("-requested_at")
        user = self.request.user
        if user.role not in SITE_SCOPE_EXEMPT_ROLES:
            warehouse_ids = list(assigned_site_ids(user, "warehouse"))
            station_ids = list(assigned_site_ids(user, "station"))
            qs = qs.filter(
                Q(warehouse_id__in=warehouse_ids) | Q(station_id__in=station_ids) | Q(requested_by=user)
            )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_status"] = self.request.GET.get("status", "")
        return ctx


class StockRequestDetailView(CapabilityRequiredMixin, DetailView):
    capability = "station_request.view"
    model = StockRequest
    template_name = "requests/stock_request_detail.html"
    context_object_name = "req"
    queryset = StockRequest.objects.select_related("station", "warehouse", "requested_by", "approved_by").prefetch_related(
        "lines__product"
    )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reject_form"] = StockRequestRejectForm()
        return ctx


class StockRequestApproveView(CapabilityRequiredMixin, View):
    capability = "station_request.approve"

    def post(self, request, pk):
        req = get_object_or_404(StockRequest, pk=pk)
        ensure_site_access(request.user, warehouse_id=req.warehouse_id)
        try:
            services.approve_request(request_id=pk, approved_by=request.user)
            messages.success(request, f"Request #{pk} approved.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("stock_requests_web:detail", args=[pk]))


class StockRequestRejectView(CapabilityRequiredMixin, View):
    capability = "station_request.approve"

    def post(self, request, pk):
        req = get_object_or_404(StockRequest, pk=pk)
        ensure_site_access(request.user, warehouse_id=req.warehouse_id)
        form = StockRequestRejectForm(request.POST)
        if form.is_valid():
            try:
                services.reject_request(request_id=pk, approved_by=request.user, reason=form.cleaned_data["reason"])
                messages.success(request, f"Request #{pk} rejected.")
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "A rejection reason is required.")
        return redirect(reverse("stock_requests_web:detail", args=[pk]))


class StockRequestDispatchView(CapabilityRequiredMixin, View):
    capability = "warehouse.stock.manage"

    def post(self, request, pk):
        req = get_object_or_404(StockRequest, pk=pk)
        ensure_site_access(request.user, warehouse_id=req.warehouse_id)
        try:
            _, shortfall = services.dispatch_request(request_id=pk, dispatched_by=request.user)
            if shortfall:
                messages.warning(request, "Dispatched what stock was available; some lines are short.")
            else:
                messages.success(request, f"Request #{pk} fully dispatched.")
        except RequestNotApprovedError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("stock_requests_web:detail", args=[pk]))


class StockRequestCreateView(CapabilityRequiredMixin, View):
    capability = "station_request.create"
    template_name = "requests/stock_request_form.html"

    def get(self, request, station_id):
        station = get_object_or_404(Station, pk=station_id)
        ensure_site_access(request.user, station_id=station_id)
        return render(
            request, self.template_name,
            {"station": station, "warehouse_form": StockRequestWarehouseForm(), "formset": StockRequestLineFormSet()},
        )

    def post(self, request, station_id):
        station = get_object_or_404(Station, pk=station_id)
        ensure_site_access(request.user, station_id=station_id)
        warehouse_form = StockRequestWarehouseForm(request.POST)
        formset = StockRequestLineFormSet(request.POST)
        if warehouse_form.is_valid() and formset.is_valid():
            lines = [
                {"product_id": f.cleaned_data["product"].id, "quantity": f.cleaned_data["quantity"]}
                for f in formset
                if f.cleaned_data.get("product") and f.cleaned_data.get("quantity")
            ]
            if not lines:
                messages.error(request, "Add at least one product and quantity.")
            else:
                req = services.create_request(
                    station_id=station_id, warehouse_id=warehouse_form.cleaned_data["warehouse"].id,
                    requested_by=request.user, lines=lines,
                )
                messages.success(request, "Stock request submitted.")
                return redirect(reverse("stock_requests_web:detail", args=[req.pk]))
        return render(
            request, self.template_name,
            {"station": station, "warehouse_form": warehouse_form, "formset": formset},
        )
