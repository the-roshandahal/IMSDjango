from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CapabilityRequiredMixin
from apps.employees import services
from apps.employees.forms import EmployeeEditForm, EmployeeOnboardingForm, EmployeeQuickAddForm
from apps.employees.models import Employee


class EmployeeListView(CapabilityRequiredMixin, ListView):
    capability = "employee.view"
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"
    paginate_by = 50

    def get_queryset(self):
        qs = Employee.objects.all()
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

    def get_context_data(self, **kwargs):
        from apps.core.permissions import has_capability

        ctx = super().get_context_data(**kwargs)
        can_manage = has_capability(self.request.user, "employee.manage")
        ctx["can_manage"] = can_manage
        if can_manage:
            ctx["invite_link"] = services.onboarding_url(self.request, self.object)
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

    def form_valid(self, form):
        messages.success(self.request, f"{form.instance.full_name} updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employees_web:detail", args=[self.object.pk])


class EmployeeResendInviteView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
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
        employee = get_object_or_404(Employee, pk=pk)
        services.deactivate(employee)
        messages.success(request, f"{employee.full_name} deactivated.")
        return redirect(reverse("employees_web:detail", args=[pk]))


class EmployeeReactivateView(CapabilityRequiredMixin, View):
    capability = "employee.manage"

    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        services.reactivate(employee)
        messages.success(request, f"{employee.full_name} reactivated.")
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
