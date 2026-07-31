from django import forms

from apps.accounts.models import User
from apps.equipment.models import Equipment, TestResult, TestTag
from apps.warehouses.models import Station, Warehouse


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


class TestTagForm(forms.ModelForm):
    class Meta:
        model = TestTag
        fields = ["name", "station", "warehouse", "start_date", "expiry_date", "comment"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = Station.objects.filter(is_active=True)
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("station") and not cleaned.get("warehouse"):
            raise forms.ValidationError("Pick a station or warehouse for this tag's location.")
        start = cleaned.get("start_date")
        expiry = cleaned.get("expiry_date")
        if start and expiry and expiry <= start:
            raise forms.ValidationError("Expiry date must be after the start date.")
        return cleaned
