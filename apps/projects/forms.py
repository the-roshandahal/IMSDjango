from decimal import Decimal

from django import forms

from apps.accounts.models import Role, User
from apps.catalogue.models import Product
from apps.equipment.models import Equipment, EquipmentStatus
from apps.projects.models import DeepCleanProject, Shift
from apps.vehicles.models import Vehicle, VehicleStatus
from apps.warehouses.models import Station, Warehouse


class ProjectForm(forms.ModelForm):
    class Meta:
        model = DeepCleanProject
        fields = ["reference", "name", "station", "supervisor", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {"end_date": "Leave blank if not yet known -- can run a single day up to several weeks."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = Station.objects.filter(is_active=True)
        self.fields["supervisor"].queryset = User.objects.filter(role=Role.DEEPCLEAN_SUPERVISOR, is_active=True)


class ProjectDispatchForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True), label="From warehouse")
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ProjectReturnForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_archived=False))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True), label="Return to warehouse")
    quantity = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ProjectEquipmentAssignForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.filter(status=EquipmentStatus.AVAILABLE))
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    override = forms.BooleanField(required=False, label="Override maintenance/test block")
    override_reason = forms.CharField(required=False, label="Override reason")


class ProjectVehicleAssignForm(forms.Form):
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.filter(status=VehicleStatus.AVAILABLE))
    driver = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True), required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    override = forms.BooleanField(required=False, label="Override compliance block")
    override_reason = forms.CharField(required=False, label="Override reason")


class ShiftLogForm(forms.Form):
    work_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    shift = forms.ChoiceField(choices=Shift.choices)
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    workers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True), required=False, widget=forms.SelectMultiple(attrs={"size": 6}),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ProjectCloseForm(forms.Form):
    override = forms.BooleanField(required=False, label="Override outstanding equipment/vehicles")
    override_reason = forms.CharField(required=False, label="Override reason", widget=forms.Textarea(attrs={"rows": 2}))
