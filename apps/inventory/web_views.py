from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, has_capability
from apps.inventory import forms as inv_forms
from apps.inventory import services
from apps.inventory.exceptions import ApprovalRequiredError, InsufficientStockError, StockLevelChangedError
from apps.inventory.models import InventoryTransaction, Stocktake

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


class TransactionAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not (has_capability(request.user, "warehouse.stock.manage") or has_capability(request.user, "transaction.view")):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class TransactionListView(TransactionAccessMixin, ListView):
    model = InventoryTransaction
    template_name = "inventory/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 40

    def get_queryset(self):
        qs = InventoryTransaction.objects.select_related(
            "product", "batch", "source_warehouse", "dest_warehouse", "station", "project", "performed_by"
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
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(reason_code__icontains=q) | Q(comment__icontains=q) | Q(product__name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["types"] = InventoryTransaction._meta.get_field("type").choices
        ctx["active_type"] = self.request.GET.get("type", "")
        ctx["q"] = self.request.GET.get("q", "")
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
            purpose = data["purpose"]
            reason_code = data["reason_code"] or purpose
            comment = data["comment"]
            station = data.get("station")
            if purpose == inv_forms.StockOutForm.PURPOSE_DEEP_CLEAN:
                comment = f"Deep clean project: {data['project_reference']}. {comment}".strip()
            return services.stock_out(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=user, station_id=station.id if station else None,
                reason_code=reason_code, comment=comment,
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


def _can_view_stocktakes(user) -> bool:
    return has_capability(user, "stocktake.manage") or has_capability(user, "stocktake.view")


def _stocktake_sites(user):
    """(warehouses, stations) the user may run a stocktake at."""
    from apps.warehouses.models import Station, Warehouse

    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return Warehouse.objects.filter(is_active=True), Station.objects.filter(is_active=True)
    warehouse_ids = list(assigned_site_ids(user, "warehouse"))
    station_ids = list(assigned_site_ids(user, "station"))
    return (
        Warehouse.objects.filter(pk__in=warehouse_ids, is_active=True),
        Station.objects.filter(pk__in=station_ids, is_active=True),
    )


class StocktakeAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not _can_view_stocktakes(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class StocktakeListView(StocktakeAccessMixin, ListView):
    model = Stocktake
    template_name = "inventory/stocktake_list.html"
    context_object_name = "stocktakes"
    paginate_by = 30

    def get_queryset(self):
        qs = Stocktake.objects.select_related("warehouse", "station", "started_by")
        user = self.request.user
        if user.role not in SITE_SCOPE_EXEMPT_ROLES:
            warehouse_ids = list(assigned_site_ids(user, "warehouse"))
            station_ids = list(assigned_site_ids(user, "station"))
            qs = qs.filter(Q(warehouse_id__in=warehouse_ids) | Q(station_id__in=station_ids))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_start"] = has_capability(self.request.user, "stocktake.manage")
        return ctx


class StocktakeDetailView(StocktakeAccessMixin, DetailView):
    model = Stocktake
    template_name = "inventory/stocktake_detail.html"
    context_object_name = "stocktake"

    def get_queryset(self):
        return Stocktake.objects.select_related("warehouse", "station", "started_by").prefetch_related("lines__product")


class StocktakeCreateView(StocktakeAccessMixin, View):
    template_name = "inventory/stocktake_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not has_capability(request.user, "stocktake.manage"):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from apps.catalogue.models import Product

        warehouses, stations = _stocktake_sites(request.user)
        site_type = request.GET.get("site_type")
        site_id = request.GET.get("site_id")

        if not site_type or not site_id:
            return render(request, self.template_name, {"warehouses": warehouses, "stations": stations})

        site = self._get_site(site_type, site_id, warehouses, stations)
        if site is None:
            messages.error(request, "Pick a warehouse or station to start a stocktake.")
            return redirect(reverse("inventory_web:stocktake-new"))

        products = Product.objects.filter(is_archived=False).select_related("category").order_by("category__name", "name")
        form = inv_forms.StocktakeCountForm(products=products)
        current_stock = self._current_stock(site_type, site, products)
        return render(request, self.template_name, {
            "site": site, "site_type": site_type, "products": products, "form": form,
            "current_stock": current_stock, "rows": self._rows(products, form, current_stock),
        })

    def post(self, request):
        from apps.catalogue.models import Product

        site_type = request.POST.get("site_type")
        site_id = request.POST.get("site_id")
        warehouses, stations = _stocktake_sites(request.user)
        site = self._get_site(site_type, site_id, warehouses, stations)
        if site is None:
            messages.error(request, "Pick a warehouse or station to start a stocktake.")
            return redirect(reverse("inventory_web:stocktake-new"))

        products = Product.objects.filter(is_archived=False).select_related("category").order_by("category__name", "name")
        current_stock = self._current_stock(site_type, site, products)
        form = inv_forms.StocktakeCountForm(request.POST, products=products)
        if not form.is_valid():
            messages.error(request, "Check the quantities entered and try again.")
            return render(request, self.template_name, {
                "site": site, "site_type": site_type, "products": products, "form": form, "current_stock": current_stock,
                "rows": self._rows(products, form, current_stock),
            })

        lines = form.counted_lines()
        if not lines:
            messages.error(request, "Enter at least one counted quantity.")
            return render(request, self.template_name, {
                "site": site, "site_type": site_type, "products": products, "form": form, "current_stock": current_stock,
                "rows": self._rows(products, form, current_stock),
            })

        try:
            stocktake = services.create_stocktake(
                started_by=request.user, lines=lines,
                warehouse_id=site.pk if site_type == "warehouse" else None,
                station_id=site.pk if site_type == "station" else None,
            )
        except StockLevelChangedError as exc:
            messages.error(request, str(exc) + " Please try again.")
            return render(request, self.template_name, {
                "site": site, "site_type": site_type, "products": products, "form": form, "current_stock": current_stock,
                "rows": self._rows(products, form, current_stock),
            })

        messages.success(request, f"Stocktake recorded -- {len(lines)} product(s) counted at {site}.")
        return redirect(reverse("inventory_web:stocktake-detail", args=[stocktake.pk]))

    @staticmethod
    def _get_site(site_type, site_id, warehouses, stations):
        try:
            site_id = int(site_id)
        except (TypeError, ValueError):
            return None
        if site_type == "warehouse":
            return warehouses.filter(pk=site_id).first()
        if site_type == "station":
            return stations.filter(pk=site_id).first()
        return None

    @staticmethod
    def _current_stock(site_type, site, products):
        from django.db.models import Sum

        from apps.inventory.models import StockLevel

        filters = {"warehouse_id": site.pk} if site_type == "warehouse" else {"station_id": site.pk}
        rows = (
            StockLevel.objects.filter(product__in=products, project=None, **filters)
            .values("product_id").annotate(total=Sum("quantity"))
        )
        return {row["product_id"]: row["total"] for row in rows}

    @staticmethod
    def _rows(products, form, current_stock):
        from itertools import groupby

        grouped = []
        for category_name, items in groupby(products, key=lambda p: p.category.name if p.category_id else "Uncategorised"):
            grouped.append({
                "category": category_name,
                "items": [
                    {"product": p, "field": form[f"qty_{p.id}"], "current": current_stock.get(p.id, 0)}
                    for p in items
                ],
            })
        return grouped
