from django import forms


class LoginForm(forms.Form):
    identifier = forms.CharField(label="Email or username")
    password = forms.CharField(widget=forms.PasswordInput)


class TwoFactorForm(forms.Form):
    token = forms.CharField(label="Authentication code", max_length=12)
