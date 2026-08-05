import datetime

from django import forms

from apps.attendance.models import DutySheet


def _time_choices(step_minutes=15):
    """Quarter-hour options for a shift start/end time, e.g. "6:00 AM" --
    a plain <select> beats the browser's native time spinner: consistent
    styling across browsers, no fiddly click-to-increment UI, and it still
    opens a native wheel picker on mobile."""
    choices = [("", "Select a time")]
    t = datetime.datetime(2000, 1, 1)
    for _ in range(24 * 60 // step_minutes):
        choices.append((t.strftime("%H:%M"), t.strftime("%I:%M %p").lstrip("0")))
        t += datetime.timedelta(minutes=step_minutes)
    return choices


TIME_CHOICES = _time_choices()


class TimeChoiceField(forms.TypedChoiceField):
    """A quarter-hour <select> that cleans straight into a datetime.time --
    used in place of the model's plain TimeField on forms below."""

    def __init__(self, **kwargs):
        kwargs.setdefault("choices", TIME_CHOICES)
        kwargs.setdefault("coerce", lambda v: datetime.datetime.strptime(v, "%H:%M").time())
        super().__init__(**kwargs)

    def prepare_value(self, value):
        if isinstance(value, datetime.time):
            return value.strftime("%H:%M")
        return super().prepare_value(value)


class DutySheetForm(forms.ModelForm):
    tasks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "placeholder": "One task per line, e.g.\nSweep platform\nEmpty bins\nMop concourse"}),
        label="Tasks", help_text="One task per line. This checklist is permanent -- reused every day.",
    )
    start_time = TimeChoiceField(label="Start time")
    end_time = TimeChoiceField(label="End time")

    class Meta:
        model = DutySheet
        fields = ["name", "start_time", "end_time"]

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

    start_time = TimeChoiceField(label="Start time")
    end_time = TimeChoiceField(label="End time")

    class Meta:
        model = DutySheet
        fields = ["name", "start_time", "end_time"]

    def clean_name(self):
        name = self.cleaned_data["name"]
        if DutySheet.objects.filter(station=self.instance.station, name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A duty sheet with this name already exists at this station.")
        return name


class AddTaskForm(forms.Form):
    description = forms.CharField(max_length=255)
