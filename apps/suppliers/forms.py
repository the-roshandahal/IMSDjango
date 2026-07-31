from django import forms

from apps.catalogue.models import Product
from apps.suppliers.models import Supplier, SupplierProduct


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "notes", "is_active"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class SupplierProductForm(forms.ModelForm):
    class Meta:
        model = SupplierProduct
        fields = ["product", "unit_price", "supplier_sku", "lead_time_days", "is_preferred"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_archived=False)
