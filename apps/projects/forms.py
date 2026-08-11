from decimal import Decimal

from django import forms

from apps.accounts.models import Role, User
from apps.catalogue.models import Product
from apps.employees.models import Employee
from apps.equipment.models import Equipment, EquipmentStatus
from apps.projects.models import DeepCleanProject, Shift
from apps.vehicles.models import Vehicle, VehicleStatus
from apps.warehouses.models import Warehouse


class ProjectForm(forms.ModelForm):
    class Meta:
        model = DeepCleanProject
        fields = ["reference", "name", "location", "supervisor", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {"end_date": "Leave blank if not yet known -- can run a single day up to several weeks."}
        labels = {"location": "Location"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].required = True
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
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True), required=False, label="Crew",
        widget=forms.CheckboxSelectMultiple,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


TOOLBOX_AUDIENCE_ALL = "all"
TOOLBOX_AUDIENCE_SELECTED = "selected"
TOOLBOX_AUDIENCE_PROJECT_TEAM = "project_team"

TOOLBOX_AUDIENCE_CHOICES = [
    (TOOLBOX_AUDIENCE_ALL, "All employees"),
    (TOOLBOX_AUDIENCE_SELECTED, "Selected employees"),
    (TOOLBOX_AUDIENCE_PROJECT_TEAM, "Everyone on a project"),
]


class ToolboxTalkForm(forms.Form):
    work_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    topic = forms.CharField(max_length=200, help_text="e.g. 'Wet floors & chemical handling'")
    content = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 4}), help_text="Hazards discussed, controls, PPE required.",
    )
    attachment = forms.FileField(
        required=False, label="Attach a file (optional)",
        help_text="The toolbox talk paper/form, if you have one -- PDF, image, Word or Excel.",
    )
    project = forms.ModelChoiceField(
        queryset=DeepCleanProject.objects.none(), required=False, label="Project (optional)",
        help_text="Leave blank for a general talk. Shows on the project's page either way you send it.",
    )
    audience = forms.ChoiceField(
        choices=TOOLBOX_AUDIENCE_CHOICES, widget=forms.RadioSelect, initial=TOOLBOX_AUDIENCE_ALL, label="Send to",
    )
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True), required=False, label="Attendees",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, projects=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = projects if projects is not None else DeepCleanProject.objects.none()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("content") and not cleaned.get("attachment"):
            raise forms.ValidationError("Add some briefing content, attach a file, or both.")

        audience = cleaned.get("audience")
        project = cleaned.get("project")
        if audience == TOOLBOX_AUDIENCE_SELECTED and not cleaned.get("employees"):
            raise forms.ValidationError('Pick at least one attendee, or choose a different "Send to" option.')
        if audience == TOOLBOX_AUDIENCE_PROJECT_TEAM:
            if not project:
                raise forms.ValidationError('Pick a project to send to "Everyone on a project".')
            elif not project.team.exists():
                raise forms.ValidationError(f"{project.name} has no team members yet -- add some on the project page first.")
        return cleaned

    def resolve_employees(self):
        """The actual employees to send this talk to, based on the chosen
        audience -- call only after is_valid() has passed."""
        audience = self.cleaned_data["audience"]
        if audience == TOOLBOX_AUDIENCE_ALL:
            return list(Employee.objects.filter(is_active=True))
        if audience == TOOLBOX_AUDIENCE_PROJECT_TEAM:
            return list(self.cleaned_data["project"].team.filter(is_active=True))
        return list(self.cleaned_data["employees"])


class ProjectTeamAddForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.filter(is_active=True), label="Add employee")


class ProjectCloseForm(forms.Form):
    override = forms.BooleanField(required=False, label="Override outstanding equipment/vehicles")
    override_reason = forms.CharField(required=False, label="Override reason", widget=forms.Textarea(attrs={"rows": 2}))
