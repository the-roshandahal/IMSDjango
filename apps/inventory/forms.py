from decimal import Decimal

from django import forms

from apps.catalogue.models import Batch, Product
from apps.vehicles.models import Vehicle, VehicleStatus
from apps.warehouses.models import Station, Warehouse


class ThresholdForm(forms.Form):
    reorder_point = forms.IntegerField(
        min_value=0, required=False, label="Low-stock threshold at this site",
        help_text="Leave blank to use this product's default reorder point instead of a site-specific one.",
    )


class StockInForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    reason_code = forms.CharField(required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class StockOutForm(forms.Form):
    PURPOSE_STATION = "station"
    PURPOSE_VEHICLE = "vehicle"
    PURPOSE_DEEP_CLEAN = "deep_clean"
    PURPOSE_WRITE_OFF = "write_off"
    PURPOSE_OTHER = "other"
    PURPOSE_CHOICES = [
        (PURPOSE_STATION, "Issue to a station"),
        (PURPOSE_VEHICLE, "Issue to a vehicle"),
        (PURPOSE_DEEP_CLEAN, "Deep clean project"),
        (PURPOSE_WRITE_OFF, "Write-off / consumed directly"),
        (PURPOSE_OTHER, "Other"),
    ]

    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True))
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    purpose = forms.ChoiceField(choices=PURPOSE_CHOICES, initial=PURPOSE_STATION, label="Dispatching for")
    station = forms.ModelChoiceField(
        queryset=Station.objects.filter(is_active=True), required=False, label="Station",
    )
    vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.exclude(status=VehicleStatus.WRITTEN_OFF), required=False, label="Vehicle",
    )
    project_reference = forms.CharField(
        required=False, label="Deep clean project reference",
        help_text="Project name/reference, client, or job number -- kept on the transaction record.",
    )
    reason_code = forms.CharField(required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        purpose = cleaned.get("purpose")
        if purpose == self.PURPOSE_STATION and not cleaned.get("station"):
            self.add_error("station", "Choose a station when dispatching for station issue.")
        if purpose == self.PURPOSE_VEHICLE and not cleaned.get("vehicle"):
            self.add_error("vehicle", "Choose a vehicle when dispatching for vehicle restock.")
        if purpose == self.PURPOSE_DEEP_CLEAN and not cleaned.get("project_reference"):
            self.add_error("project_reference", "Enter a project reference for deep clean dispatches.")
        return cleaned


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
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.all(), required=False)
    reason_code = forms.CharField(required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("station") and cleaned.get("vehicle"):
            raise forms.ValidationError("Return from a station or a vehicle, not both.")
        return cleaned


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


class VehicleUsageForm(forms.Form):
    vehicle_id = forms.IntegerField(widget=forms.HiddenInput)
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False)


class StocktakeCountForm(forms.Form):
    """One optional field per product -- left blank means 'not checked
    this time', not 'zero on hand' (SRS: not every product gets counted
    on every weekly stocktake)."""

    def __init__(self, *args, products=(), **kwargs):
        super().__init__(*args, **kwargs)
        for product in products:
            self.fields[f"qty_{product.id}"] = forms.DecimalField(
                required=False, min_value=Decimal("0"), decimal_places=2, max_digits=12, label=product.name,
            )

    def counted_lines(self):
        lines = []
        for name, value in self.cleaned_data.items():
            if value is None:
                continue
            product_id = int(name.split("_", 1)[1])
            lines.append({"product_id": product_id, "counted_quantity": value})
        return lines
