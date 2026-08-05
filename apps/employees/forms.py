from django import forms

from apps.employees.models import Employee


class EmployeeStationAssignForm(forms.Form):
    station = forms.ModelChoiceField(queryset=None, label="Station")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.warehouses.models import Station

        self.fields["station"].queryset = Station.objects.filter(is_active=True)


class EmployeeQuickAddForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "email", "phone", "position"]
        help_texts = {"position": "e.g. Station Cleaner, Team Leader"}


class EmployeeEditForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "first_name", "last_name", "email", "phone", "position", "date_started",
            "dob", "address", "riw_number", "riw_expiry_date",
            "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
            "notes",
        ]
        widgets = {
            "date_started": forms.DateInput(attrs={"type": "date"}),
            "dob": forms.DateInput(attrs={"type": "date"}),
            "riw_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class EmployeeOnboardingForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "dob", "address", "riw_number", "riw_expiry_date",
            "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
        ]
        widgets = {
            "dob": forms.DateInput(attrs={"type": "date"}),
            "riw_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "riw_number": "RIW number",
            "riw_expiry_date": "RIW card expiry date",
        }
