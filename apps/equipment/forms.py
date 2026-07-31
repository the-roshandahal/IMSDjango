from django import forms

from apps.accounts.models import User
from apps.equipment.models import Equipment, TestResult
from apps.warehouses.models import Station


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ["asset_id", "name", "serial_number", "maintenance_interval_days", "test_interval_days"]
        help_texts = {
            "maintenance_interval_days": "Days between scheduled maintenance. Leave blank if not on a fixed schedule.",
            "test_interval_days": "Days between electrical safety tests (default 365 = annual).",
        }


class EquipmentAssignForm(forms.Form):
    station = forms.ModelChoiceField(queryset=Station.objects.filter(is_active=True))
    assigned_user = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True), required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    override = forms.BooleanField(required=False, label="Override maintenance/test block")
    override_reason = forms.CharField(required=False, label="Override reason", widget=forms.TextInput)


class EquipmentReleaseForm(forms.Form):
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class EquipmentMaintenanceForm(forms.Form):
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class EquipmentTestForm(forms.Form):
    result = forms.ChoiceField(choices=TestResult.choices)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
