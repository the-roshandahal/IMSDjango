from decimal import Decimal

import bleach
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


# The rich text editor on the create page only ever produces these tags --
# anything else (script, style, on* attributes, iframe, ...) is stripped on
# save. Keeps the briefing content safe to render unescaped everywhere it's
# shown (detail page, the public sign-off page, the PDF export).
TOOLBOX_CONTENT_ALLOWED_TAGS = ["p", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li", "h3", "h4", "blockquote"]

# Pre-fills the editor on a new talk with the company's own standing TBT
# checklist (from the paper form) -- a starting point to trim/edit per talk
# rather than retyping the same standard checks every time.
TOOLBOX_CONTENT_DEFAULT = """<h3>1. Start of Shift Meeting</h3>
<ul>
<li>Discuss today's job and tasks</li>
<li>Assign clear roles to each team member</li>
</ul>
<h3>2. Uniform &amp; PPE Check</h3>
<ul>
<li>All staff wearing correct uniform (long sleeves, pants, approved safety shoes)</li>
<li>PPE worn correctly: gloves, safety glasses, masks, etc.</li>
</ul>
<h3>3. Safety &amp; Hazards</h3>
<ul>
<li>Discuss site hazards</li>
<li>Use wet floor signs at all times</li>
<li>Never leave trolleys or vans unattended</li>
<li>Always report hazards to the supervisor</li>
</ul>
<h3>4. Equipment Check</h3>
<ul>
<li>Use correct mops with wooden handles when working on platforms</li>
<li>Keep equipment and products tidy and organised</li>
<li>Store items safely - do not block walkways</li>
</ul>
<h3>5. Task-Specific Reminders</h3>
<ul>
<li><b>Escalator cleaning:</b> barricade the area; if escalator is running, no one is allowed near it</li>
<li><b>High dusting:</b> wear safety glasses, use correct PPE, avoid electrical areas, use approved extension poles</li>
<li><b>Chewing gum removal:</b> use correct scraper; do NOT use orange solvent on painted surfaces or aluminium</li>
<li><b>Pressure washing:</b> never spray higher than 30cm towards ledges; do not pressure wash walls or ceilings; always check hose position to prevent tripping hazards</li>
</ul>
<h3>6. Personnel Responsibility</h3>
<ul>
<li>Keys and access cards must always stay with staff members</li>
<li>If unsure or confused, ask your supervisor</li>
<li>If challenged or feeling unsafe, contact your supervisor immediately</li>
</ul>
<h3>7. End of Shift Responsibilities</h3>
<ul>
<li>Collect and dispose of all rubbish on site or at the warehouse</li>
<li>Van, Ute, and Truck cabins must be wiped and cleaned after returning to the warehouse</li>
<li>Restock all boxes and prepare vehicles for the next dispatch</li>
<li>Waterproof cloths: check and empty pockets, place in washing machine, turn on, and message managers so cloths can be hung to dry in the morning</li>
<li>Mop heads, dusters, and sponges to be disposed of at the end of each project</li>
</ul>"""


class ToolboxTalkForm(forms.Form):
    work_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    topic = forms.CharField(max_length=200, help_text="e.g. 'Wet floors & chemical handling'")
    content = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Hazards discussed, controls, PPE required.",
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

    def clean_content(self):
        content = self.cleaned_data.get("content", "")
        return bleach.clean(content, tags=TOOLBOX_CONTENT_ALLOWED_TAGS, attributes={}, strip=True)

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
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True), label="Add employees",
        widget=forms.CheckboxSelectMultiple,
    )


class ProjectCloseForm(forms.Form):
    override = forms.BooleanField(required=False, label="Override outstanding equipment/vehicles")
    override_reason = forms.CharField(required=False, label="Override reason", widget=forms.Textarea(attrs={"rows": 2}))
