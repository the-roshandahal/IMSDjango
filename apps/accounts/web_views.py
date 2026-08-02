import datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import services
from apps.accounts.forms import (
    LoginForm,
    PermissionChecklistForm,
    SiteAssignmentForm,
    TwoFactorForm,
    UserCreateForm,
    UserDeactivateForm,
    UserRoleForm,
)
from apps.accounts.models import Role, SiteAssignment, User, UserCapabilityOverride
from apps.audit.models import AuditLog
from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import (
    CAPABILITY_CATALOG,
    SITE_SCOPE_EXEMPT_ROLES,
    assigned_site_ids,
    effective_capabilities,
    role_default_capability,
    set_capability_overrides,
)
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
            from apps.core.case_studies import get_all_case_studies

            return render(request, "core/home.html", {"case_studies": get_all_case_studies()})

        from apps.catalogue.models import Product
        from apps.inventory.models import InventoryTransaction
        from apps.requests.models import StockRequest, StockRequestStatus
        from apps.warehouses.models import Station, Warehouse

        user = request.user
        exempt = user.role in SITE_SCOPE_EXEMPT_ROLES
        warehouse_ids = None if exempt else list(assigned_site_ids(user, "warehouse"))
        station_ids = None if exempt else list(assigned_site_ids(user, "station"))

        warehouses_qs = Warehouse.objects.filter(is_active=True)
        stations_qs = Station.objects.filter(is_active=True)
        if not exempt:
            warehouses_qs = warehouses_qs.filter(pk__in=warehouse_ids)
            stations_qs = stations_qs.filter(pk__in=station_ids)

        products_qs = Product.objects.filter(is_archived=False)

        stock_filter = Q(stock_levels__warehouse__isnull=False)
        if not exempt:
            stock_filter &= Q(stock_levels__warehouse_id__in=warehouse_ids)
        low_stock_qs = (
            products_qs.annotate(total_stock=Sum("stock_levels__quantity", filter=stock_filter))
            .filter(total_stock__isnull=False, total_stock__lte=F("reorder_point"))
            .order_by("total_stock")
        )
        low_stock_count = low_stock_qs.count()
        low_stock_products = low_stock_qs[:8]

        pending_requests_qs = StockRequest.objects.filter(status=StockRequestStatus.PENDING)
        if not exempt:
            pending_requests_qs = pending_requests_qs.filter(
                Q(warehouse_id__in=warehouse_ids) | Q(station_id__in=station_ids)
            )
        pending_requests = pending_requests_qs.select_related("station", "warehouse").order_by("-requested_at")[:6]

        txns_qs = InventoryTransaction.objects.select_related("product", "performed_by", "source_warehouse", "dest_warehouse", "station")
        if not exempt:
            txns_qs = txns_qs.filter(
                Q(source_warehouse_id__in=warehouse_ids) | Q(dest_warehouse_id__in=warehouse_ids) | Q(station_id__in=station_ids)
            )
        recent_transactions = txns_qs.order_by("-timestamp")[:20]

        context = {
            "total_products": products_qs.count(),
            "total_warehouses": warehouses_qs.count(),
            "total_stations": stations_qs.count(),
            "low_stock_products": low_stock_products,
            "low_stock_count": low_stock_count,
            "pending_requests": pending_requests,
            "pending_requests_count": pending_requests_qs.count(),
            "recent_transactions": recent_transactions,
        }

        if user.role == Role.ADMIN:
            context["total_users"] = User.objects.count()
            context["locked_users_count"] = User.objects.filter(locked_until__gt=timezone.now()).count()
            context["recent_audit"] = AuditLog.objects.select_related("actor").order_by("-timestamp")[:8]

        from apps.core.permissions import has_capability

        if has_capability(user, "equipment.assign") or has_capability(user, "vehicle.assign"):
            from apps.equipment.models import Equipment
            from apps.vehicles.models import Vehicle

            today = timezone.now().date()
            context["equipment_maintenance_due_count"] = Equipment.objects.filter(
                next_maintenance_due__lte=today
            ).exclude(status="written_off").count()
            context["equipment_test_issues_count"] = Equipment.objects.filter(
                Q(next_test_due__lte=today) | Q(last_test_result="fail")
            ).exclude(status="written_off").count()
            context["vehicle_service_due_count"] = Vehicle.objects.filter(
                service_due_date__lte=today
            ).exclude(status="written_off").count()
            context["vehicle_insurance_expired_count"] = Vehicle.objects.filter(
                insurance_expiry__lte=today
            ).exclude(status="written_off").count()

            from apps.equipment.models import TestTag

            context["test_tags_expired_count"] = TestTag.objects.filter(expiry_date__lte=today).count()
            context["test_tags_expiring_count"] = TestTag.objects.filter(
                expiry_date__gt=today, expiry_date__lte=today + timezone.timedelta(days=TestTag.EXPIRY_WARNING_DAYS)
            ).count()

        return render(request, self.template_name, context)


# ---------------------------------------------------------------------
# User management (SRS Section 5.1 / 8.2). Capability "user.manage" is
# only granted to admin (via the "*" wildcard in ROLE_CAPABILITIES), so
# gating every view on it is effectively admin-only without a separate
# role check.
# ---------------------------------------------------------------------

class UserListView(CapabilityRequiredMixin, ListView):
    capability = "user.manage"
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    queryset = User.objects.all().prefetch_related("site_assignments").order_by("username")


class UserDetailView(CapabilityRequiredMixin, DetailView):
    capability = "user.manage"
    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "target_user"
    queryset = User.objects.all().prefetch_related("site_assignments__warehouse", "site_assignments__station")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["role_form"] = UserRoleForm(initial={"role": self.object.role})
        ctx["deactivate_form"] = UserDeactivateForm()
        ctx["site_form"] = SiteAssignmentForm()
        ctx["pending_blockers"] = services.check_pending_assets(self.object) if self.object.is_active else []
        ctx["active_overrides"] = self.object.capability_overrides.all()
        return ctx


class UserCreateView(CapabilityRequiredMixin, CreateView):
    capability = "user.manage"
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.log(actor=self.request.user, action="user.created", entity_type="User", entity_id=self.object.pk)
        messages.success(self.request, f"User {self.object.username} created.")
        return response

    def get_success_url(self):
        return reverse("accounts:user-detail-page", args=[self.object.pk])


class UserRoleChangeWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        form = UserRoleForm(request.POST)
        if form.is_valid():
            old_role = user_obj.role
            user_obj.role = form.cleaned_data["role"]
            user_obj.save(update_fields=["role"])
            AuditLog.log(
                actor=request.user, action="user.role_changed", entity_type="User", entity_id=user_obj.pk,
                metadata={"old_role": old_role, "new_role": user_obj.role},
            )
            messages.success(request, "Role updated.")
        return redirect(reverse("accounts:user-detail-page", args=[pk]))


class UserDeactivateWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        form = UserDeactivateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "A reason is required to deactivate a user.")
            return redirect(reverse("accounts:user-detail-page", args=[pk]))

        blockers = services.check_pending_assets(user_obj)
        override = form.cleaned_data["override"]
        if blockers and not override:
            messages.error(request, "Cannot deactivate: " + "; ".join(blockers) + " (check Override to force it).")
            return redirect(reverse("accounts:user-detail-page", args=[pk]))

        user_obj.is_active = False
        user_obj.deactivated_at = timezone.now()
        user_obj.deactivation_reason = form.cleaned_data["reason"]
        user_obj.deactivated_by = request.user
        user_obj.save(update_fields=["is_active", "deactivated_at", "deactivation_reason", "deactivated_by"])
        AuditLog.log(
            actor=request.user, action="user.deactivated", entity_type="User", entity_id=user_obj.pk,
            metadata={"reason": form.cleaned_data["reason"], "override": override, "blockers": blockers},
        )
        messages.success(request, f"{user_obj.username} deactivated.")
        return redirect(reverse("accounts:user-detail-page", args=[pk]))


class UserReactivateWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        user_obj.is_active = True
        user_obj.deactivated_at = None
        user_obj.deactivation_reason = ""
        user_obj.deactivated_by = None
        user_obj.save(update_fields=["is_active", "deactivated_at", "deactivation_reason", "deactivated_by"])
        AuditLog.log(actor=request.user, action="user.reactivated", entity_type="User", entity_id=user_obj.pk)
        messages.success(request, f"{user_obj.username} reactivated.")
        return redirect(reverse("accounts:user-detail-page", args=[pk]))


class UserUnlockWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        user_obj.reset_lockout()
        AuditLog.log(actor=request.user, action="user.unlocked", entity_type="User", entity_id=user_obj.pk)
        messages.success(request, "Lockout cleared.")
        return redirect(reverse("accounts:user-detail-page", args=[pk]))


class UserSiteAssignmentCreateWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        form = SiteAssignmentForm(request.POST)
        if form.is_valid() and (form.cleaned_data.get("warehouse") or form.cleaned_data.get("station")):
            assignment = form.save(commit=False)
            assignment.user = user_obj
            assignment.save()
            messages.success(request, "Site assignment added.")
        else:
            messages.error(request, "Choose a warehouse or station to assign.")
        return redirect(reverse("accounts:user-detail-page", args=[pk]))


class UserSiteAssignmentDeleteWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk, assignment_id):
        SiteAssignment.objects.filter(pk=assignment_id, user_id=pk).delete()
        messages.success(request, "Site assignment removed.")
        return redirect(reverse("accounts:user-detail-page", args=[pk]))


class UserPermissionsView(CapabilityRequiredMixin, View):
    """Per-user custom permission checklist -- grant or revoke individual
    capabilities beyond what the role normally gives, optionally with an
    expiry date so it stops applying itself automatically."""

    capability = "user.manage"
    template_name = "accounts/user_permissions.html"

    def get(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        state = effective_capabilities(user_obj)
        form = PermissionChecklistForm(
            capabilities=[(cap, label) for _group, items in CAPABILITY_CATALOG for cap, label in items],
            initial_state=state,
        )
        return render(request, self.template_name, self._context(request, user_obj, form, state))

    def post(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        all_caps = [(cap, label) for _group, items in CAPABILITY_CATALOG for cap, label in items]
        form = PermissionChecklistForm(request.POST, capabilities=all_caps)
        if not form.is_valid():
            messages.error(request, "Check the form and try again.")
            return render(request, self.template_name, self._context(request, user_obj, form, effective_capabilities(user_obj)))

        expires_at = form.cleaned_data.get("expires_at")
        if expires_at:
            expires_at = timezone.make_aware(datetime.datetime.combine(expires_at, datetime.time.max))
        changed = set_capability_overrides(
            user=user_obj, grants=form.capability_grants(), granted_by=request.user,
            expires_at=expires_at, reason=form.cleaned_data.get("reason", ""),
        )
        if changed:
            AuditLog.log(
                actor=request.user, action="user.permissions_changed", entity_type="User", entity_id=user_obj.pk,
                metadata={"changes": changed, "expires_at": expires_at.isoformat() if expires_at else None},
                ip_address=get_client_ip(request),
            )
            messages.success(request, f"Updated {len(changed)} permission(s) for {user_obj.username}.")
        else:
            messages.info(request, "No changes to save.")
        return redirect(reverse("accounts:user-permissions-page", args=[pk]))

    def _context(self, request, user_obj, form, state):
        groups = []
        for group_name, items in CAPABILITY_CATALOG:
            rows = []
            for capability, label in items:
                rows.append({
                    "capability": capability, "label": label, "field": form[f"cap_{capability}"],
                    "role_default": role_default_capability(user_obj.role, capability),
                })
            groups.append({"name": group_name, "rows": rows})
        return {
            "target_user": user_obj, "form": form, "groups": groups,
            "active_overrides": user_obj.capability_overrides.all(),
        }


class UserPermissionOverrideDeleteWebView(CapabilityRequiredMixin, View):
    capability = "user.manage"

    def post(self, request, pk, override_id):
        UserCapabilityOverride.objects.filter(pk=override_id, user_id=pk).delete()
        messages.success(request, "Permission override removed -- back to the role default.")
        return redirect(reverse("accounts:user-permissions-page", args=[pk]))
