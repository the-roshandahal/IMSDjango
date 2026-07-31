import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, ensure_site_access, has_capability
from apps.purchasing import services
from apps.purchasing.forms import (
    CancelPurchaseOrderForm,
    PurchaseOrderHeaderForm,
    PurchaseOrderLineAddForm,
    PurchaseOrderLineFormSet,
    ReceiveLineForm,
)
from apps.purchasing.models import PurchaseOrder
from apps.purchasing.services import LineChangedError
from apps.suppliers.models import SupplierProduct


def _can_view(user) -> bool:
    return has_capability(user, "purchase_order.manage") or has_capability(user, "purchase_order.view")


class PurchaseOrderAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not _can_view(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class PurchaseOrderListView(PurchaseOrderAccessMixin, ListView):
    model = PurchaseOrder
    template_name = "purchasing/po_list.html"
    context_object_name = "purchase_orders"
    paginate_by = 30

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related("supplier", "warehouse")
        user = self.request.user
        if user.role not in SITE_SCOPE_EXEMPT_ROLES:
            qs = qs.filter(warehouse_id__in=list(assigned_site_ids(user, "warehouse")))
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage"] = has_capability(self.request.user, "purchase_order.manage")
        ctx["active_status"] = self.request.GET.get("status", "")
        return ctx


class PurchaseOrderDetailView(PurchaseOrderAccessMixin, DetailView):
    model = PurchaseOrder
    template_name = "purchasing/po_detail.html"
    context_object_name = "po"
    queryset = PurchaseOrder.objects.select_related("supplier", "warehouse", "created_by").prefetch_related("lines__product")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        can_manage = has_capability(self.request.user, "purchase_order.manage")
        ctx["can_manage"] = can_manage
        if can_manage:
            ctx["add_line_form"] = PurchaseOrderLineAddForm()
            ctx["receive_form"] = ReceiveLineForm()
            ctx["cancel_form"] = CancelPurchaseOrderForm()
            prices = {
                str(sp.product_id): str(sp.unit_price)
                for sp in SupplierProduct.objects.filter(supplier_id=self.object.supplier_id)
            }
            ctx["supplier_prices_json"] = json.dumps(prices)

        from apps.documents.services import documents_for

        ctx["documents"] = documents_for(self.object)
        ctx["can_manage_documents"] = can_manage
        ctx["document_model_key"] = "purchasing.purchaseorder"
        ctx["document_object_id"] = self.object.pk
        return ctx


class PurchaseOrderCreateView(PurchaseOrderAccessMixin, View):
    template_name = "purchasing/po_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not has_capability(request.user, "purchase_order.manage"):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def _supplier_prices(self):
        prices = {}
        for sp in SupplierProduct.objects.all():
            prices.setdefault(str(sp.supplier_id), {})[str(sp.product_id)] = str(sp.unit_price)
        return json.dumps(prices)

    def get(self, request):
        return render(
            request, self.template_name,
            {
                "header_form": PurchaseOrderHeaderForm(), "formset": PurchaseOrderLineFormSet(),
                "supplier_prices_json": self._supplier_prices(),
            },
        )

    def post(self, request):
        header_form = PurchaseOrderHeaderForm(request.POST)
        formset = PurchaseOrderLineFormSet(request.POST)
        if header_form.is_valid() and formset.is_valid():
            ensure_site_access(request.user, warehouse_id=header_form.cleaned_data["warehouse"].id)
            lines = [
                {
                    "product_id": f.cleaned_data["product"].id, "quantity": f.cleaned_data["quantity"],
                    "unit_price": f.cleaned_data["unit_price"],
                }
                for f in formset
                if f.cleaned_data.get("product") and f.cleaned_data.get("quantity") is not None
                and f.cleaned_data.get("unit_price") is not None
            ]
            if not lines:
                messages.error(request, "Add at least one product, quantity, and unit price.")
            else:
                po = services.create_purchase_order(
                    supplier_id=header_form.cleaned_data["supplier"].id,
                    warehouse_id=header_form.cleaned_data["warehouse"].id,
                    expected_date=header_form.cleaned_data["expected_date"],
                    notes=header_form.cleaned_data["notes"], created_by=request.user, lines=lines,
                )
                messages.success(request, f"Purchase order {po.reference} created as a draft.")
                return redirect(reverse("purchasing_web:detail", args=[po.pk]))
        return render(
            request, self.template_name,
            {"header_form": header_form, "formset": formset, "supplier_prices_json": self._supplier_prices()},
        )


def _require_manage(request, po):
    if not has_capability(request.user, "purchase_order.manage"):
        raise PermissionDenied()
    ensure_site_access(request.user, warehouse_id=po.warehouse_id)


class PurchaseOrderSendView(PurchaseOrderAccessMixin, View):
    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        _require_manage(request, po)
        try:
            services.send(po_id=pk, performed_by=request.user)
            messages.success(request, f"{po.reference} sent to {po.supplier.name}.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("purchasing_web:detail", args=[pk]))


class PurchaseOrderCancelView(PurchaseOrderAccessMixin, View):
    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        _require_manage(request, po)
        form = CancelPurchaseOrderForm(request.POST)
        if not form.is_valid():
            messages.error(request, "A cancellation reason is required.")
            return redirect(reverse("purchasing_web:detail", args=[pk]))
        try:
            services.cancel(po_id=pk, performed_by=request.user, reason=form.cleaned_data["reason"])
            messages.success(request, f"{po.reference} cancelled.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("purchasing_web:detail", args=[pk]))


class PurchaseOrderLineAddView(PurchaseOrderAccessMixin, View):
    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        _require_manage(request, po)
        if not po.is_editable:
            messages.error(request, "Lines can only be added to a draft purchase order.")
            return redirect(reverse("purchasing_web:detail", args=[pk]))
        form = PurchaseOrderLineAddForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the product, quantity, and price.")
            return redirect(reverse("purchasing_web:detail", args=[pk]))
        data = form.cleaned_data
        if po.lines.filter(product_id=data["product"].id).exists():
            messages.error(request, f"{data['product'].name} is already on this order.")
        else:
            po.lines.create(product_id=data["product"].id, quantity_ordered=data["quantity"], unit_price=data["unit_price"])
            messages.success(request, f"{data['product'].name} added.")
        return redirect(reverse("purchasing_web:detail", args=[pk]))


class PurchaseOrderLineRemoveView(PurchaseOrderAccessMixin, View):
    def post(self, request, pk, line_id):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        _require_manage(request, po)
        if not po.is_editable:
            messages.error(request, "Lines can only be removed from a draft purchase order.")
            return redirect(reverse("purchasing_web:detail", args=[pk]))
        line = get_object_or_404(po.lines, pk=line_id)
        product_name = line.product.name
        line.delete()
        messages.success(request, f"{product_name} removed.")
        return redirect(reverse("purchasing_web:detail", args=[pk]))


class PurchaseOrderReceiveLineView(PurchaseOrderAccessMixin, View):
    def post(self, request, pk, line_id):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        _require_manage(request, po)
        form = ReceiveLineForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid quantity received.")
            return redirect(reverse("purchasing_web:detail", args=[pk]))
        try:
            services.receive_line(line_id=line_id, quantity=form.cleaned_data["quantity"], performed_by=request.user)
            messages.success(request, "Receipt recorded and warehouse stock updated.")
        except (ValueError, LineChangedError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("purchasing_web:detail", args=[pk]))


class PurchaseOrderPrintView(PurchaseOrderAccessMixin, DetailView):
    model = PurchaseOrder
    template_name = "purchasing/po_print.html"
    context_object_name = "po"
    queryset = PurchaseOrder.objects.select_related("supplier", "warehouse", "created_by").prefetch_related("lines__product")
