from django import forms

from apps.employees.models import Employee

ANNOUNCEMENT_AUDIENCE_ALL = "all"
ANNOUNCEMENT_AUDIENCE_SELECTED = "selected"

ANNOUNCEMENT_AUDIENCE_CHOICES = [
    (ANNOUNCEMENT_AUDIENCE_ALL, "All employees"),
    (ANNOUNCEMENT_AUDIENCE_SELECTED, "Selected employees"),
]


class AnnouncementForm(forms.Form):
    title = forms.CharField(max_length=200, help_text="e.g. 'New PPE supplier from Monday'")
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}))
    audience = forms.ChoiceField(
        choices=ANNOUNCEMENT_AUDIENCE_CHOICES, widget=forms.RadioSelect, initial=ANNOUNCEMENT_AUDIENCE_ALL, label="Send to",
    )
    # Only employees with a login can actually receive this -- announcements
    # ride the existing Notification system, which is strictly per-User.
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True, user__isnull=False), required=False, label="Recipients",
        widget=forms.CheckboxSelectMultiple,
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("audience") == ANNOUNCEMENT_AUDIENCE_SELECTED and not cleaned.get("employees"):
            raise forms.ValidationError('Pick at least one recipient, or choose "All employees".')
        return cleaned

    def resolve_employees(self):
        """The actual employees to notify, based on the chosen audience --
        call only after is_valid() has passed."""
        if self.cleaned_data["audience"] == ANNOUNCEMENT_AUDIENCE_ALL:
            return list(Employee.objects.filter(is_active=True, user__isnull=False))
        return list(self.cleaned_data["employees"])
