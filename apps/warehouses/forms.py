from django import forms

from apps.warehouses.models import Station, Warehouse


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["name", "address", "capacity"]


class StationForm(forms.ModelForm):
    class Meta:
        model = Station
        fields = ["name", "address"]
