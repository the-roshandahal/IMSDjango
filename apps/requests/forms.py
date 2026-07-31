from decimal import Decimal

from django import forms
from django.forms import formset_factory

from apps.catalogue.models import Product
from apps.warehouses.models import Warehouse


class StockRequestWarehouseForm(forms.Form):
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))


class StockRequestLineForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False), required=False)
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12, required=False)


StockRequestLineFormSet = formset_factory(StockRequestLineForm, extra=5, can_delete=False)


class StockRequestRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
