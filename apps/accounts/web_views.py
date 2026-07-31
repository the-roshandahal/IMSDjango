from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import services
from apps.accounts.forms import LoginForm, TwoFactorForm
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip


class LoginPageView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse_lazy("accounts:dashboard"))
        return render(request, self.template_name, {"form": LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user, result = services.check_credentials(
            form.cleaned_data["identifier"], form.cleaned_data["password"], request=request
        )
        ip = get_client_ip(request)

        if result == services.LoginResult.OK:
            login(request, user)
            AuditLog.log(actor=user, action="auth.login_success", entity_type="User", entity_id=user.pk, ip_address=ip)
            return redirect(reverse_lazy("accounts:dashboard"))

        if result == services.LoginResult.REQUIRES_2FA:
            request.session["pending_2fa_user_id"] = user.pk
            return redirect(reverse_lazy("accounts:login-2fa"))

        messages_by_result = {
            services.LoginResult.INVALID_CREDENTIALS: "Invalid credentials.",
            services.LoginResult.LOCKED: "Account is locked. Try again later or contact an administrator.",
            services.LoginResult.INACTIVE: "Account is deactivated.",
        }
        AuditLog.log(
            actor=user, action=f"auth.login_failed.{result}", entity_type="User",
            entity_id=user.pk if user else "", ip_address=ip,
        )
        messages.error(request, messages_by_result.get(result, "Login failed."))
        return render(request, self.template_name, {"form": form})


class TwoFactorPageView(View):
    template_name = "accounts/two_factor.html"

    def get(self, request):
        if not request.session.get("pending_2fa_user_id"):
            return redirect(reverse_lazy("accounts:login"))
        return render(request, self.template_name, {"form": TwoFactorForm()})

    def post(self, request):
        pending_id = request.session.get("pending_2fa_user_id")
        if not pending_id:
            return redirect(reverse_lazy("accounts:login"))

        form = TwoFactorForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = User.objects.filter(pk=pending_id, is_active=True).first()
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first() if user else None
        if user is None or device is None or not device.verify_token(form.cleaned_data["token"]):
            messages.error(request, "Invalid code.")
            return render(request, self.template_name, {"form": form})

        del request.session["pending_2fa_user_id"]
        login(request, user)
        AuditLog.log(actor=user, action="auth.login_success", entity_type="User", entity_id=user.pk)
        return redirect(reverse_lazy("accounts:dashboard"))


class LogoutPageView(View):
    def post(self, request):
        if request.user.is_authenticated:
            AuditLog.log(actor=request.user, action="auth.logout", entity_type="User", entity_id=request.user.pk)
        logout(request)
        return redirect(reverse_lazy("accounts:login"))

    def get(self, request):
        return self.post(request)


class DashboardView(View):
    template_name = "accounts/dashboard.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect(reverse_lazy("accounts:login"))
        return render(request, self.template_name, {"user": request.user})
