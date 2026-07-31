from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids
from apps.inventory import forms as inv_forms
from apps.inventory import services
from apps.inventory.exceptions import ApprovalRequiredError, InsufficientStockError, StockLevelChangedError
from apps.inventory.models import InventoryTransaction

ACTION_FORMS = {
    "stock_in": inv_forms.StockInForm,
    "stock_out": inv_forms.StockOutForm,
    "transfer": inv_forms.TransferForm,
    "adjustment": inv_forms.AdjustmentForm,
    "return": inv_forms.ReturnForm,
    "damaged": inv_forms.DamagedForm,
    "lost": inv_forms.LostForm,
    "expired": inv_forms.ExpiredForm,
}
ACTION_LABELS = {
    "stock_in": "Stock in",
    "stock_out": "Stock out",
    "transfer": "Transfer",
    "adjustment": "Adjustment",
    "return": "Return",
    "damaged": "Damaged",
    "lost": "Lost",
    "expired": "Expired",
}


class TransactionListView(CapabilityRequiredMixin, ListView):
    capability = "warehouse.stock.manage"
    model = InventoryTransaction
    template_name = "inventory/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 40

    def get_queryset(self):
        qs = InventoryTransaction.objects.select_related(
            "product", "batch", "source_warehouse", "dest_warehouse", "station", "performed_by"
        ).order_by("-timestamp")
        user = self.request.user
        if user.role not in SITE_SCOPE_EXEMPT_ROLES:
            warehouse_ids = list(assigned_site_ids(user, "warehouse"))
            station_ids = list(assigned_site_ids(user, "station"))
            qs = qs.filter(
                Q(source_warehouse_id__in=warehouse_ids)
                | Q(dest_warehouse_id__in=warehouse_ids)
                | Q(station_id__in=station_ids)
            )
        txn_type = self.request.GET.get("type")
        if txn_type:
            qs = qs.filter(type=txn_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["types"] = InventoryTransaction._meta.get_field("type").choices
        ctx["active_type"] = self.request.GET.get("type", "")
        return ctx


class NewTransactionView(CapabilityRequiredMixin, View):
    capability = "warehouse.stock.manage"
    template_name = "inventory/new_transaction.html"

    def _blank_forms(self, active, warehouse_initial=None):
        forms_dict = {}
        for key, form_cls in ACTION_FORMS.items():
            initial = {}
            if warehouse_initial and "warehouse" in form_cls.base_fields:
                initial["warehouse"] = warehouse_initial
            if warehouse_initial and "source_warehouse" in form_cls.base_fields:
                initial["source_warehouse"] = warehouse_initial
            forms_dict[key] = form_cls(initial=initial)
        return forms_dict

    def get(self, request):
        active = request.GET.get("type", "stock_in")
        if active not in ACTION_FORMS:
            active = "stock_in"
        forms_dict = self._blank_forms(active, request.GET.get("warehouse"))
        return render(request, self.template_name, {"forms": forms_dict, "active": active, "labels": ACTION_LABELS})

    def post(self, request):
        action = request.POST.get("action_type")
        form_cls = ACTION_FORMS.get(action)
        if form_cls is None:
            messages.error(request, "Unknown action.")
            return redirect(reverse("inventory_web:new-transaction"))

        form = form_cls(request.POST, request.FILES)
        if not form.is_valid():
            forms_dict = self._blank_forms(action)
            forms_dict[action] = form
            return render(request, self.template_name, {"forms": forms_dict, "active": action, "labels": ACTION_LABELS})

        try:
            self._dispatch(action, form.cleaned_data, request.user)
        except (InsufficientStockError, StockLevelChangedError, ApprovalRequiredError, ValueError) as exc:
            messages.error(request, str(exc))
            forms_dict = self._blank_forms(action)
            forms_dict[action] = form
            return render(request, self.template_name, {"forms": forms_dict, "active": action, "labels": ACTION_LABELS})

        messages.success(request, f"{ACTION_LABELS[action]} recorded.")
        return redirect(reverse("inventory_web:transaction-list"))

    def _dispatch(self, action, data, user):
        if action == "stock_in":
            return services.stock_in(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=user, reason_code=data["reason_code"], comment=data["comment"],
            )
        if action == "stock_out":
            return services.stock_out(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=user, station_id=data["station"].id if data.get("station") else None,
                reason_code=data["reason_code"], comment=data["comment"],
            )
        if action == "transfer":
            return services.transfer_initiate(
                product_id=data["product"].id, quantity=data["quantity"],
                source_warehouse_id=data["source_warehouse"].id, initiated_by=user,
                dest_warehouse_id=data["dest_warehouse"].id if data.get("dest_warehouse") else None,
                dest_station_id=data["dest_station"].id if data.get("dest_station") else None,
                comment=data["comment"],
            )
        if action == "adjustment":
            return services.adjustment(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id,
                quantity_delta=data["quantity_delta"], performed_by=user,
                reason_code=data["reason_code"], comment=data["comment"],
            )
        if action == "return":
            return services.return_stock(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=user, station_id=data["station"].id if data.get("station") else None,
                reason_code=data["reason_code"], comment=data["comment"],
            )
        if action == "damaged":
            return services.record_damaged(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=user, comment=data["comment"], photo=data.get("photo"),
            )
        if action == "lost":
            return services.record_lost(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=user, approved_by=user, comment=data["comment"],
            )
        if action == "expired":
            return services.record_expired(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, batch_id=data["batch"].id,
                quantity=data["quantity"], performed_by=user, comment=data["comment"],
            )
        raise ValueError(f"Unknown action '{action}'.")


class StationUsageWebView(CapabilityRequiredMixin, View):
    capability = "station.usage.record"

    def post(self, request):
        form = inv_forms.StationUsageForm(request.POST)
        redirect_url = reverse("warehouses_web:station-detail", args=[request.POST.get("station_id") or 0])
        if not form.is_valid():
            messages.error(request, "Could not record usage: check the form and try again.")
            return redirect(redirect_url)
        data = form.cleaned_data
        try:
            services.station_stock_usage(
                product_id=data["product_id"], station_id=data["station_id"], quantity=data["quantity"],
                performed_by=request.user, comment=data["comment"],
            )
        except (StockLevelChangedError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Usage recorded.")
        return redirect(reverse("warehouses_web:station-detail", args=[data["station_id"]]))
