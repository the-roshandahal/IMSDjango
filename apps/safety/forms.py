from django import forms

from apps.safety.models import HazardReport


class HazardReportForm(forms.ModelForm):
    class Meta:
        model = HazardReport
        fields = [
            "report_type", "severity", "title", "description", "location_detail",
            "immediate_action_taken", "injury_involved", "photo",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "immediate_action_taken": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "immediate_action_taken": "Immediate action taken (if any)",
            "injury_involved": "Someone was injured",
        }


class HazardResolveForm(forms.Form):
    corrective_action = forms.CharField(
        label="Corrective action taken", widget=forms.Textarea(attrs={"rows": 3})
    )
