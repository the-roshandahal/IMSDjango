from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.accounts.models import Role
from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, has_capability
from apps.safety import services
from apps.safety.forms import HazardReportForm, HazardResolveForm
from apps.safety.models import HazardReport, HazardStatus


def _hazard_sites(user):
    """Stations/projects this user is allowed to file or view a hazard
    report against -- mirrors the access rules ProjectListView and the
    station SiteAssignment scoping already use, so "where can I report
    this from" always matches "what can I otherwise see"."""
    from apps.projects.models import DeepCleanProject, ProjectStatus
    from apps.warehouses.models import Station

    stations = Station.objects.filter(is_active=True)
    projects = DeepCleanProject.objects.exclude(status=ProjectStatus.COMPLETED)

    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return stations.order_by("name"), projects.order_by("-start_date")

    station_ids = list(assigned_site_ids(user, "station"))
    stations = stations.filter(pk__in=station_ids)
    if user.role == Role.DEEPCLEAN_SUPERVISOR:
        projects = projects.filter(supervisor=user)
    else:
        projects = projects.none()
    return stations.order_by("name"), projects.order_by("-start_date")


def _get_hazard_site(site_type, site_id, stations, projects):
    try:
        site_id = int(site_id)
    except (TypeError, ValueError):
        return None
    if site_type == "station":
        return stations.filter(pk=site_id).first()
    if site_type == "project":
        return projects.filter(pk=site_id).first()
    return None


def _scoped_hazard_queryset(user):
    qs = HazardReport.objects.select_related("station", "project", "reported_by", "resolved_by")
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return qs
    station_ids = list(assigned_site_ids(user, "station"))
    return qs.filter(
        Q(station_id__in=station_ids) | Q(project__supervisor=user) | Q(reported_by=user)
    ).distinct()


def _can_manage_report(user, report) -> bool:
    if not has_capability(user, "hazard.manage"):
        return False
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return True
    if report.station_id:
        return report.station_id in set(assigned_site_ids(user, "station"))
    return report.project.supervisor_id == user.id


class HazardAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not (has_capability(request.user, "hazard.view") or has_capability(request.user, "hazard.report")):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class HazardReportListView(HazardAccessMixin, ListView):
    model = HazardReport
    template_name = "safety/hazard_list.html"
    context_object_name = "reports"
    paginate_by = 30

    def get_queryset(self):
        qs = _scoped_hazard_queryset(self.request.user)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        severity = self.request.GET.get("severity")
        if severity:
            qs = qs.filter(severity=severity)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_status"] = self.request.GET.get("status", "")
        ctx["active_severity"] = self.request.GET.get("severity", "")
        ctx["open_count"] = _scoped_hazard_queryset(self.request.user).filter(status=HazardStatus.OPEN).count()
        return ctx


class HazardReportDetailView(HazardAccessMixin, DetailView):
    model = HazardReport
    template_name = "safety/hazard_detail.html"
    context_object_name = "report"

    def get_queryset(self):
        return _scoped_hazard_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage"] = _can_manage_report(self.request.user, self.object)
        ctx["resolve_form"] = HazardResolveForm()
        return ctx


class HazardReportCreateView(CapabilityRequiredMixin, View):
    """`hazard.report` is granted to every role by default -- filing a
    hazard/incident report is meant to be universal -- but still runs
    through the capability system so a per-user override can revoke it
    for one account without touching everyone else (see the custom RBAC
    checklist on a user's profile). What differs by role day-to-day is
    only which stations/projects show up to pick from (_hazard_sites)."""

    capability = "hazard.report"
    template_name = "safety/hazard_form.html"

    def get(self, request):
        stations, projects = _hazard_sites(request.user)
        site_type = request.GET.get("site_type")
        site_id = request.GET.get("site_id")
        if not site_type or not site_id:
            return render(request, self.template_name, {"stations": stations, "projects": projects})

        site = _get_hazard_site(site_type, site_id, stations, projects)
        if site is None:
            messages.error(request, "Pick a station or deep clean project to report against.")
            return redirect(reverse("safety_web:new"))

        form = HazardReportForm()
        return render(request, self.template_name, {"site": site, "site_type": site_type, "form": form})

    def post(self, request):
        stations, projects = _hazard_sites(request.user)
        site_type = request.POST.get("site_type")
        site_id = request.POST.get("site_id")
        site = _get_hazard_site(site_type, site_id, stations, projects)
        if site is None:
            messages.error(request, "Pick a station or deep clean project to report against.")
            return redirect(reverse("safety_web:new"))

        form = HazardReportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"site": site, "site_type": site_type, "form": form})

        report = services.create_hazard_report(
            reported_by=request.user,
            station=site if site_type == "station" else None,
            project=site if site_type == "project" else None,
            **form.cleaned_data,
        )
        messages.success(request, "Hazard report submitted -- the site supervisor has been notified.")
        return redirect(reverse("safety_web:detail", args=[report.pk]))


class HazardReportResolveView(CapabilityRequiredMixin, View):
    capability = "hazard.manage"

    def post(self, request, pk):
        report = get_object_or_404(HazardReport, pk=pk)
        if not _can_manage_report(request.user, report):
            raise PermissionDenied()

        form = HazardResolveForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter the corrective action taken.")
            return redirect(reverse("safety_web:detail", args=[pk]))

        services.resolve_hazard_report(
            report=report, resolved_by=request.user, corrective_action=form.cleaned_data["corrective_action"]
        )
        messages.success(request, "Hazard report closed out.")
        return redirect(reverse("safety_web:detail", args=[pk]))
