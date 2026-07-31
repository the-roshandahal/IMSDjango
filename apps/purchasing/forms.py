from decimal import Decimal

from django import forms
from django.forms import formset_factory

from apps.catalogue.models import Product
from apps.suppliers.models import Supplier
from apps.warehouses.models import Warehouse


class PurchaseOrderHeaderForm(forms.Form):
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.filter(is_active=True))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    expected_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class PurchaseOrderLineForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False), required=False)
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12, required=False)
    unit_price = forms.DecimalField(min_value=Decimal("0"), decimal_places=2, max_digits=12, required=False)


PurchaseOrderLineFormSet = formset_factory(PurchaseOrderLineForm, extra=6, can_delete=False)


class PurchaseOrderLineAddForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    unit_price = forms.DecimalField(min_value=Decimal("0"), decimal_places=2, max_digits=12)


class ReceiveLineForm(forms.Form):
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)


class CancelPurchaseOrderForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
