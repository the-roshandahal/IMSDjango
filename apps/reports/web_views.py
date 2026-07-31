from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views.generic import TemplateView

from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, has_capability
from apps.reports import services
from apps.reports.forms import DateRangeForm


def _default_range(request):
    form = DateRangeForm(request.GET)
    today = timezone.now().date()
    date_from = form.data.get("date_from") or (today - timedelta(days=30))
    date_to = form.data.get("date_to") or today
    if form.is_valid():
        date_from = form.cleaned_data["date_from"] or (today - timedelta(days=30))
        date_to = form.cleaned_data["date_to"] or today
    return date_from, date_to


class ReportAccessMixin(LoginRequiredMixin):
    required_capabilities = ()  # any-of

    def dispatch(self, request, *args, **kwargs):
        if not any(has_capability(request.user, cap) for cap in self.required_capabilities):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class ReportHubView(ReportAccessMixin, TemplateView):
    template_name = "reports/hub.html"
    required_capabilities = ("reports.view", "reports.view_own_site", "reports.view_own_project")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["can_reports_view"] = has_capability(user, "reports.view")
        ctx["can_view_own_site"] = has_capability(user, "reports.view_own_site")
        ctx["can_view_own_project"] = has_capability(user, "reports.view_own_project")
        return ctx


def _my_warehouse_ids(user):
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return None
    return list(assigned_site_ids(user, "warehouse"))


def _my_station_ids(user):
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return None
    return list(assigned_site_ids(user, "station"))


class InventoryReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/inventory.html"
    required_capabilities = ("reports.view", "reports.view_own_site")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        warehouse_ids = _my_warehouse_ids(self.request.user)
        ctx["on_hand"] = services.inventory_on_hand(warehouse_ids)
        ctx["value"] = services.inventory_value(warehouse_ids)
        ctx["ageing"] = services.inventory_ageing(warehouse_ids)
        ctx["expiry"] = services.inventory_expiry(warehouse_ids=warehouse_ids)
        return ctx


class ConsumptionReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/consumption.html"
    required_capabilities = ("reports.view", "reports.view_own_site", "reports.view_own_project")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from, date_to = _default_range(self.request)
        user = self.request.user
        project_ids = None
        if user.role not in SITE_SCOPE_EXEMPT_ROLES and has_capability(user, "reports.view_own_project") and not has_capability(user, "reports.view"):
            from apps.projects.models import DeepCleanProject
            project_ids = list(DeepCleanProject.objects.filter(supervisor=user).values_list("id", flat=True))
        report = services.consumption_report(
            date_from, date_to, warehouse_ids=_my_warehouse_ids(user), station_ids=_my_station_ids(user),
            project_ids=project_ids,
        )
        ctx.update(report)
        ctx["date_from"], ctx["date_to"] = date_from, date_to
        return ctx


class EquipmentReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/equipment.html"
    required_capabilities = ("reports.view",)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from, date_to = _default_range(self.request)
        ctx.update(services.equipment_report(date_from, date_to))
        ctx["date_from"], ctx["date_to"] = date_from, date_to
        return ctx


class ProjectReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/projects.html"
    required_capabilities = ("reports.view", "reports.view_own_project")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        project_ids = None
        if not has_capability(user, "reports.view"):
            from apps.projects.models import DeepCleanProject
            project_ids = list(DeepCleanProject.objects.filter(supervisor=user).values_list("id", flat=True))
        status = self.request.GET.get("status") or None
        ctx["rows"] = services.project_report(status=status, project_ids=project_ids)
        ctx["active_status"] = status or ""
        return ctx


class PurchasingReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/purchasing.html"
    required_capabilities = ("reports.view", "reports.view_own_site")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from, date_to = _default_range(self.request)
        ctx.update(services.purchasing_report(date_from, date_to, warehouse_ids=_my_warehouse_ids(self.request.user)))
        ctx["date_from"], ctx["date_to"] = date_from, date_to
        return ctx


class VehicleReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/vehicles.html"
    required_capabilities = ("reports.view",)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from, date_to = _default_range(self.request)
        ctx.update(services.vehicle_report(date_from, date_to))
        ctx["date_from"], ctx["date_to"] = date_from, date_to
        return ctx


class AuditReportView(ReportAccessMixin, TemplateView):
    template_name = "reports/audit.html"
    required_capabilities = ("reports.view",)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from, date_to = _default_range(self.request)
        ctx.update(services.audit_report(date_from, date_to))
        ctx["date_from"], ctx["date_to"] = date_from, date_to
        return ctx
