from django import forms

from apps.documents.models import Document


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["file", "description"]
        widgets = {"description": forms.TextInput(attrs={"placeholder": "Optional description"})}
