from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES
from apps.employees import services
from apps.employees.forms import EmployeeEditForm, EmployeeOnboardingForm, EmployeeQuickAddForm, EmployeeStationAssignForm
from apps.employees.models import Employee


def _visible_employees_for(user):
    """Company-wide for exempt roles (wh_supervisor/admin -- same
    company-wide oversight they already get everywhere else). Any other
    role holding employee.view/manage (currently only deepclean_supervisor)
    is scoped to employees on a project they supervise, or that they
    personally created -- the `created_by` half matters so adding a brand
    new employee doesn't immediately 404 you out of their own detail page
    before you've had a chance to add them to a project's team."""
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return Employee.objects.all()
    return Employee.objects.filter(Q(deep_clean_projects__supervisor=user) | Q(created_by=user)).distinct()


class EmployeeListView(CapabilityRequiredMixin, ListView):
    capability = "employee.view"
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"
    paginate_by = 50

    def get_queryset(self):
        qs = _visible_employees_for(self.request.user)
        status = self.request.GET.get("status", "")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q

            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        from apps.core.permissions import has_capability

        ctx = super().get_context_data(**kwargs)
        ctx["can_manage"] = has_capability(self.request.user, "employee.manage")
        ctx["active_status"] = self.request.GET.get("status", "")
        ctx["query"] = self.request.GET.get("q", "")
        return ctx


class EmployeeDetailView(CapabilityRequiredMixin, DetailView):
    capability = "employee.view"
    model = Employee
    template_name = "employees/employee_detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return _visible_employees_for(self.request.user)

    def get_context_data(self, **kwargs):
        from apps.core.permissions import has_capability

        ctx = super().get_context_data(**kwargs)
        can_manage = has_capability(self.request.user, "employee.manage")
        ctx["can_manage"] = can_manage
        if can_manage:
            ctx["invite_link"] = services.onboarding_url(self.request, self.object)
            if self.object.user_id:
                ctx["site_assignments"] = self.object.user.site_assignments.select_related("station").order_by("station__name")
                ctx["site_assignment_form"] = EmployeeStationAssignForm()
        return ctx


class EmployeeCreateView(CapabilityRequiredMixin, CreateView):
    capability = "employee.manage"
    model = Employee
    form_class = EmployeeQuickAddForm
    template_name = "employees/employee_form.html"

    def form_valid(self, form):
        employee = services.create_employee(
            first_name=form.cleaned_data["first_name"], last_name=form.cleaned_data["last_name"],
            email=form.cleaned_data["email"], phone=form.cleaned_data["phone"],
            position=form.cleaned_data["position"], created_by=self.request.user, request=self.request,
        )
        self.object = employee
        link = services.onboarding_url(self.request, employee)
        messages.success(
            self.request,
            f"{employee.full_name} added. Onboarding link (also emailed to {employee.email}): {link}",
        )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("employees_web:detail", args=[self.object.pk])


class EmployeeUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "employee.manage"
    model = Employee
    form_class = EmployeeEditForm
    template_name = "employees/employee_form.html"

    def get_queryset(self):
        return _visible_employees_for(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, f"{form.instance.full_name} updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employees_web:detail", args=[self.object.pk])


class EmployeeResendInviteView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        sent = services.send_invite_email(employee, request, sent_by=request.user)
        link = services.onboarding_url(request, employee)
        if sent:
            messages.success(request, f"Invite re-sent to {employee.email}. Link: {link}")
        else:
            messages.warning(request, f"Couldn't send the email -- share this link directly: {link}")
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeDeactivateView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        services.deactivate(employee)
        messages.success(request, f"{employee.full_name} deactivated.")
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeReactivateView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        services.reactivate(employee)
        messages.success(request, f"{employee.full_name} reactivated.")
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeCreateLoginView(CapabilityRequiredMixin, View):
    """Grants clock-in access -- creates the linked User account. Station
    assignment happens right here on the employee page too (see the two
    views below), no detour through the accounts app needed for the
    common case."""

    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        try:
            user, temp_password = services.create_employee_login(employee=employee)
            messages.success(
                request,
                f"Login created for {employee.full_name}: username {user.username}, temporary password {temp_password}. "
                f"Assign them to a station below and share these details -- they should change the password on first login.",
            )
        except services.EmployeeLoginError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeSetKioskPinView(CapabilityRequiredMixin, View):
    """Generates a fresh 4-digit PIN for the shared NFC kiosk -- tap the
    tag, pick your name, enter this. Shown once, same "share it out of
    band" pattern as the temp password from Create login."""

    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        try:
            pin = services.set_kiosk_pin(employee=employee)
            messages.success(request, f"Kiosk PIN for {employee.full_name}: {pin}. Share it with them directly -- it won't be shown again.")
        except services.EmployeeLoginError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeSiteAssignmentCreateView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        if not employee.user_id:
            messages.error(request, "Create a login first.")
            return redirect(reverse("employees_web:detail", args=[pk]))

        form = EmployeeStationAssignForm(request.POST)
        if form.is_valid():
            from apps.accounts.models import SiteAssignment

            SiteAssignment.objects.get_or_create(user=employee.user, station=form.cleaned_data["station"])
            messages.success(request, f"{employee.full_name} assigned to {form.cleaned_data['station'].name}.")
        else:
            messages.error(request, "Pick a station.")
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeSiteAssignmentDeleteView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk, assignment_id):
        from apps.accounts.models import SiteAssignment

        employee = get_object_or_404(_visible_employees_for(request.user), pk=pk)
        SiteAssignment.objects.filter(pk=assignment_id, user=employee.user).delete()
        messages.success(request, "Station assignment removed.")
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeOnboardingView(View):
    """Public, tokenized self-service form -- no login. An employee can
    revisit their own link any time to keep RIW expiry etc. current."""

    template_name = "employees/employee_onboarding.html"

    def get(self, request, token):
        employee = Employee.objects.filter(invite_token=token).first()
        if not employee or not employee.is_active:
            return render(request, self.template_name, {"invalid": True})
        form = EmployeeOnboardingForm(instance=employee)
        return render(request, self.template_name, {"employee": employee, "form": form})

    def post(self, request, token):
        employee = Employee.objects.filter(invite_token=token).first()
        if not employee or not employee.is_active:
            return render(request, self.template_name, {"invalid": True})
        form = EmployeeOnboardingForm(request.POST, instance=employee)
        if not form.is_valid():
            return render(request, self.template_name, {"employee": employee, "form": form})
        services.complete_onboarding(employee=employee, **form.cleaned_data)
        return render(request, self.template_name, {"employee": employee, "submitted": True})
