from django.contrib import messages
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.catalogue import services
from apps.catalogue.forms import CategoryForm, ProductCreateForm, ProductForm
from apps.catalogue.models import Category, Product
from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import has_capability
from apps.inventory import services as inventory_services


class ProductListView(CapabilityRequiredMixin, ListView):
    capability = "product.view"
    model = Product
    template_name = "catalogue/product_list.html"
    context_object_name = "products"
    paginate_by = 30

    def get_queryset(self):
        qs = (
            Product.objects.select_related("category")
            .filter(is_archived=False)
            .annotate(total_stock=Sum("stock_levels__quantity", filter=Q(stock_levels__warehouse__isnull=False)))
            .order_by("name")
        )
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(barcode__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class ProductDetailView(CapabilityRequiredMixin, DetailView):
    capability = "product.view"
    model = Product
    template_name = "catalogue/product_detail.html"
    context_object_name = "product"
    queryset = Product.objects.select_related("category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        can_view_warehouses = has_capability(self.request.user, "warehouse.view")
        ctx["can_view_warehouses"] = can_view_warehouses
        stock_levels = self.object.stock_levels.select_related("warehouse", "station", "project").filter(quantity__gt=0)
        if can_view_warehouses:
            ctx["batches"] = self.object.batches.select_related("warehouse").order_by("expiry_date")
            ctx["stock_levels"] = stock_levels
            ctx["total_stock"] = (
                self.object.stock_levels.filter(warehouse__isnull=False).aggregate(t=Sum("quantity"))["t"] or 0
            )
        else:
            ctx["batches"] = self.object.batches.none()
            ctx["stock_levels"] = stock_levels.filter(warehouse__isnull=True)
            ctx["total_stock"] = None
        from apps.documents.services import documents_for

        ctx["documents"] = documents_for(self.object)
        ctx["can_manage_documents"] = has_capability(self.request.user, "product.manage")
        ctx["document_model_key"] = "catalogue.product"
        ctx["document_object_id"] = self.object.pk
        return ctx


class ProductCreateView(CapabilityRequiredMixin, CreateView):
    """Also supports recording existing on-hand stock in the same step, for
    onboarding products the company already has (not a brand-new item)."""

    capability = "product.manage"
    model = Product
    form_class = ProductCreateForm
    template_name = "catalogue/product_form.html"

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            services.provision_codes(self.object)

            warehouse = form.cleaned_data.get("initial_warehouse")
            quantity = form.cleaned_data.get("initial_quantity")
            if warehouse and quantity:
                inventory_services.stock_in(
                    product_id=self.object.id, warehouse_id=warehouse.id, quantity=quantity,
                    performed_by=self.request.user, reason_code="onboarding",
                    comment="Existing stock recorded while adding this product to IMS.",
                )
                messages.success(self.request, f"{self.object.name} created with {quantity} on hand at {warehouse.name}.")
            else:
                messages.success(self.request, f"{self.object.name} created.")
        return response

    def get_success_url(self):
        return reverse("catalogue_web:product-detail", args=[self.object.pk])


class ProductUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "product.manage"
    model = Product
    form_class = ProductForm
    template_name = "catalogue/product_form.html"

    def get_success_url(self):
        return reverse("catalogue_web:product-detail", args=[self.object.pk])


class ProductArchiveView(CapabilityRequiredMixin, DetailView):
    """POST-only action; DetailView is reused just for get_object()."""

    capability = "product.manage"
    model = Product

    def post(self, request, *args, **kwargs):
        product = self.get_object()
        product.is_archived = True
        product.save(update_fields=["is_archived"])
        messages.success(request, f"{product.name} archived.")
        return redirect(reverse("catalogue_web:product-list"))


class ProductDeleteView(CapabilityRequiredMixin, DetailView):
    """POST-only. Products with any transaction/batch/stock-request history
    are protected at the DB level (on_delete=PROTECT) -- that history is the
    whole point of the append-only ledger, so a real delete there would be
    silently destructive. Falls back to archiving instead, with a clear
    message about why."""

    capability = "product.manage"
    model = Product

    def post(self, request, *args, **kwargs):
        product = self.get_object()
        name = product.name
        try:
            product.delete()
            messages.success(request, f"{name} deleted.")
        except ProtectedError:
            product.is_archived = True
            product.save(update_fields=["is_archived"])
            messages.warning(
                request,
                f"{name} has transaction or stock history, so it can't be permanently deleted -- "
                "archived instead. Archived products are hidden from new transactions but keep their history.",
            )
        return redirect(reverse("catalogue_web:product-list"))


class CategoryListView(CapabilityRequiredMixin, ListView):
    capability = "product.view"
    model = Category
    template_name = "catalogue/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return (
            Category.objects.select_related("parent")
            .annotate(product_count=Count("products", filter=Q(products__is_archived=False)))
            .order_by("name")
        )


class CategoryCreateView(CapabilityRequiredMixin, CreateView):
    capability = "product.manage"
    model = Category
    form_class = CategoryForm
    template_name = "catalogue/category_form.html"
    success_url = reverse_lazy("catalogue_web:category-list")
