from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.catalogue import services
from apps.catalogue.forms import CategoryForm, ProductForm
from apps.catalogue.models import Category, Product
from apps.core.mixins import CapabilityRequiredMixin


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
        ctx["batches"] = self.object.batches.select_related("warehouse").order_by("expiry_date")
        ctx["stock_levels"] = self.object.stock_levels.select_related("warehouse", "station").filter(quantity__gt=0)
        ctx["total_stock"] = (
            self.object.stock_levels.filter(warehouse__isnull=False).aggregate(t=Sum("quantity"))["t"] or 0
        )
        return ctx


class ProductCreateView(CapabilityRequiredMixin, CreateView):
    capability = "product.manage"
    model = Product
    form_class = ProductForm
    template_name = "catalogue/product_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        services.provision_codes(self.object)
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
