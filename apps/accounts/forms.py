from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.accounts.models import Role, SiteAssignment, User


class LoginForm(forms.Form):
    identifier = forms.CharField(label="Email or username")
    password = forms.CharField(widget=forms.PasswordInput)


class TwoFactorForm(forms.Form):
    token = forms.CharField(label="Authentication code", max_length=12)


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    # Model field is blank=True (deactivated/system accounts may end up
    # role-less), but a role picked at creation time is not optional --
    # a blank role means zero RBAC capabilities and a near-unusable account.
    role = forms.ChoiceField(choices=Role.choices)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "phone", "role"]

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserRoleForm(forms.Form):
    role = forms.ChoiceField(choices=Role.choices)


class UserDeactivateForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    override = forms.BooleanField(required=False, label="Override (Administrator)")


class SiteAssignmentForm(forms.ModelForm):
    class Meta:
        model = SiteAssignment
        fields = ["warehouse", "station"]


class PermissionChecklistForm(forms.Form):
    """One checkbox per capability in CAPABILITY_CATALOG, plus a shared
    optional expiry applied to whatever changes in this save."""

    expires_at = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        label="Expires on (optional)", help_text="Leave blank for permanent. Applies to whatever you change below.",
    )
    reason = forms.CharField(required=False, label="Reason (optional)", widget=forms.TextInput())

    def __init__(self, *args, capabilities=None, initial_state=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial_state = initial_state or {}
        for capability, _label in capabilities or []:
            self.fields[f"cap_{capability}"] = forms.BooleanField(
                required=False, initial=initial_state.get(capability, False),
            )

    def capability_grants(self):
        return {
            name[len("cap_"):]: bool(value)
            for name, value in self.cleaned_data.items()
            if name.startswith("cap_")
        }
