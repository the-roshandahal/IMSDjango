from django import forms

from apps.attendance.models import DutySheet


class DutySheetForm(forms.ModelForm):
    tasks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "placeholder": "One task per line, e.g.\nSweep platform\nEmpty bins\nMop concourse"}),
        label="Tasks", help_text="One task per line. This checklist is permanent -- reused every day.",
    )

    class Meta:
        model = DutySheet
        fields = ["name", "start_time", "end_time"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, station=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.station = station

    def clean_name(self):
        name = self.cleaned_data["name"]
        if self.station and DutySheet.objects.filter(station=self.station, name=name).exists():
            raise forms.ValidationError("A duty sheet with this name already exists at this station.")
        return name

    def task_descriptions(self):
        return [line for line in self.cleaned_data["tasks"].splitlines()]


class DutySheetEditForm(forms.ModelForm):
    """Editing an existing duty sheet -- name and times only. Tasks are
    managed separately (add/retire on the detail page) since they carry
    completion history that a blanket re-save shouldn't touch."""

    class Meta:
        model = DutySheet
        fields = ["name", "start_time", "end_time"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean_name(self):
        name = self.cleaned_data["name"]
        if DutySheet.objects.filter(station=self.instance.station, name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A duty sheet with this name already exists at this station.")
        return name


class AddTaskForm(forms.Form):
    description = forms.CharField(max_length=255)
