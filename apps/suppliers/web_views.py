from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import has_capability
from apps.suppliers.forms import SupplierForm, SupplierProductForm
from apps.suppliers.models import Supplier, SupplierProduct


class SupplierListView(CapabilityRequiredMixin, ListView):
    model = Supplier
    capability = "supplier.view"
    template_name = "suppliers/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 30

    def get_queryset(self):
        qs = Supplier.objects.all()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        status = self.request.GET.get("status")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage"] = has_capability(self.request.user, "supplier.manage")
        ctx["q"] = self.request.GET.get("q", "")
        ctx["active_status"] = self.request.GET.get("status", "")
        return ctx


class SupplierDetailView(CapabilityRequiredMixin, DetailView):
    model = Supplier
    capability = "supplier.view"
    template_name = "suppliers/supplier_detail.html"
    context_object_name = "supplier"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        can_manage = has_capability(self.request.user, "supplier.manage")
        ctx["can_manage"] = can_manage
        ctx["supplier_products"] = self.object.supplier_products.select_related("product").all()
        if can_manage:
            ctx["product_form"] = SupplierProductForm()
        return ctx


class SupplierCreateView(CapabilityRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    capability = "supplier.manage"
    template_name = "suppliers/supplier_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Supplier {self.object.name} created.")
        return response

    def get_success_url(self):
        return reverse("suppliers_web:detail", args=[self.object.pk])


class SupplierUpdateView(CapabilityRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    capability = "supplier.manage"
    template_name = "suppliers/supplier_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Supplier {self.object.name} updated.")
        return response

    def get_success_url(self):
        return reverse("suppliers_web:detail", args=[self.object.pk])


class SupplierProductAddView(CapabilityRequiredMixin, View):
    capability = "supplier.manage"

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk)
        form = SupplierProductForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the product/price and try again.")
            return redirect(reverse("suppliers_web:detail", args=[pk]))
        sp = form.save(commit=False)
        sp.supplier = supplier
        if SupplierProduct.objects.filter(supplier=supplier, product=sp.product).exists():
            messages.error(request, f"{sp.product.name} is already linked to this supplier.")
        else:
            sp.save()
            messages.success(request, f"{sp.product.name} added at {sp.unit_price}.")
        return redirect(reverse("suppliers_web:detail", args=[pk]))


class SupplierProductRemoveView(CapabilityRequiredMixin, View):
    capability = "supplier.manage"

    def post(self, request, pk, sp_id):
        sp = get_object_or_404(SupplierProduct, pk=sp_id, supplier_id=pk)
        product_name = sp.product.name
        sp.delete()
        messages.success(request, f"{product_name} removed from supplier.")
        return redirect(reverse("suppliers_web:detail", args=[pk]))
