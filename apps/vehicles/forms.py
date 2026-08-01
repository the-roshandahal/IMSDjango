from decimal import Decimal

from django import forms

from apps.accounts.models import User
from apps.vehicles.models import CostType, Vehicle, VehicleLocation


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["registration", "make_model", "service_due_date", "insurance_expiry"]
        widgets = {
            "service_due_date": forms.DateInput(attrs={"type": "date"}),
            "insurance_expiry": forms.DateInput(attrs={"type": "date"}),
        }


class VehicleAssignForm(forms.Form):
    location = forms.ChoiceField(choices=VehicleLocation.choices, label="Assign to")
    driver = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True), required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    override = forms.BooleanField(required=False, label="Override compliance block")
    override_reason = forms.CharField(required=False, label="Override reason")


class VehicleReleaseForm(forms.Form):
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class VehicleMaintenanceEndForm(forms.Form):
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    next_service_due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


class VehicleCostLogForm(forms.Form):
    cost_type = forms.ChoiceField(choices=CostType.choices)
    amount = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=10)
    incurred_at = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
