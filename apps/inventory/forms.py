from decimal import Decimal

from django import forms

from apps.catalogue.models import Batch, Product
from apps.warehouses.models import Station, Warehouse


class StockInForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    reason_code = forms.CharField(required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class StockOutForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    station = forms.ModelChoiceField(queryset=Station.objects.filter(is_active=True), required=False)
    reason_code = forms.CharField(required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class TransferForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    source_warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    dest_warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True), required=False)
    dest_station = forms.ModelChoiceField(queryset=Station.objects.filter(is_active=True), required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("dest_warehouse") and not cleaned.get("dest_station"):
            raise forms.ValidationError("Choose a destination warehouse or station.")
        return cleaned


class AdjustmentForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity_delta = forms.DecimalField(decimal_places=2, max_digits=12, help_text="Positive to add, negative to remove.")
    reason_code = forms.CharField()
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ReturnForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    station = forms.ModelChoiceField(queryset=Station.objects.filter(is_active=True), required=False)
    reason_code = forms.CharField(required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class DamagedForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    photo = forms.ImageField(required=False)


class LostForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ExpiredForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_batch_tracked=True, is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    batch = forms.ModelChoiceField(queryset=Batch.objects.all())
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class StationUsageForm(forms.Form):
    station_id = forms.IntegerField(widget=forms.HiddenInput)
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False)
