from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from apps.accounts.models import Role
from apps.core.permissions import has_capability
from apps.equipment import services as equipment_services
from apps.equipment.models import Equipment, EquipmentStatus
from apps.equipment.services import ComplianceBlockedError as EquipmentComplianceBlockedError
from apps.equipment.services import EquipmentUnavailableError
from apps.inventory import services as inventory_services
from apps.inventory.exceptions import InsufficientStockError, StockLevelChangedError
from apps.projects import services
from apps.projects.forms import (
    ProjectCloseForm,
    ProjectDispatchForm,
    ProjectEquipmentAssignForm,
    ProjectForm,
    ProjectReturnForm,
    ProjectVehicleAssignForm,
    ShiftLogForm,
    ToolboxTalkForm,
)
from apps.projects.models import DeepCleanProject, ToolboxTalk, ToolboxTalkAttendee
from apps.vehicles import services as vehicle_services
from apps.vehicles.models import Vehicle, VehicleStatus
from apps.vehicles.services import ComplianceBlockedError as VehicleComplianceBlockedError
from apps.vehicles.services import VehicleUnavailableError


def _can_view_projects(user) -> bool:
    return (
        has_capability(user, "project.manage")
        or has_capability(user, "project.view")
        or has_capability(user, "project.update_own")
    )


def _can_manage_project(user, project) -> bool:
    if has_capability(user, "project.manage"):
        return True
    return has_capability(user, "project.update_own") and project.supervisor_id == user.id


class ProjectAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not _can_view_projects(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class ProjectListView(ProjectAccessMixin, ListView):
    model = DeepCleanProject
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    paginate_by = 30

    def get_queryset(self):
        qs = DeepCleanProject.objects.select_related("supervisor")
        user = self.request.user
        if not (has_capability(user, "project.manage") or has_capability(user, "project.view")):
            qs = qs.filter(supervisor=user)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_create"] = has_capability(self.request.user, "project.manage")
        ctx["active_status"] = self.request.GET.get("status", "")
        return ctx


class ProjectDetailView(ProjectAccessMixin, DetailView):
    model = DeepCleanProject
    template_name = "projects/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        qs = DeepCleanProject.objects.select_related("supervisor")
        user = self.request.user
        if not (has_capability(user, "project.manage") or has_capability(user, "project.view")):
            qs = qs.filter(supervisor=user)
        return qs

    def get_context_data(self, **kwargs):
        from apps.inventory.models import StockLevel

        ctx = super().get_context_data(**kwargs)
        project = self.object
        can_manage = _can_manage_project(self.request.user, project)
        ctx["can_manage"] = can_manage
        ctx["stock"] = StockLevel.objects.filter(project=project, quantity__gt=0).select_related("product", "batch")
        ctx["equipment"] = Equipment.objects.filter(current_project=project)
        ctx["vehicles"] = Vehicle.objects.filter(current_project=project)
        ctx["shift_logs"] = project.shift_logs.prefetch_related("workers", "employees").select_related("logged_by")[:30]
        ctx["total_hours"] = sum((s.hours_worked * s.employees.count() for s in ctx["shift_logs"]), start=0)
        ctx["toolbox_talks"] = project.toolbox_talks.select_related("conducted_by").prefetch_related("attendees")[:30]
        if can_manage and project.is_open:
            ctx["dispatch_form"] = ProjectDispatchForm()
            ctx["return_form"] = ProjectReturnForm()
            ctx["equipment_form"] = ProjectEquipmentAssignForm()
            ctx["vehicle_form"] = ProjectVehicleAssignForm()
            ctx["shift_form"] = ShiftLogForm()
            ctx["toolbox_talk_form"] = ToolboxTalkForm()
            ctx["close_form"] = ProjectCloseForm()
            ctx["outstanding_assets"] = services.outstanding_assets(project)

        from apps.documents.services import documents_for

        ctx["documents"] = documents_for(project)
        ctx["can_manage_documents"] = can_manage
        ctx["document_model_key"] = "projects.deepcleanproject"
        ctx["document_object_id"] = project.pk
        return ctx


class ProjectCreateView(ProjectAccessMixin, CreateView):
    model = DeepCleanProject
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not has_capability(request.user, "project.manage"):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"Project {self.object.reference} created.")
        return response

    def get_success_url(self):
        return reverse("projects_web:detail", args=[self.object.pk])


def _require_manage(request, project):
    if not _can_manage_project(request.user, project):
        raise PermissionDenied()


class ProjectDispatchView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ProjectDispatchForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the dispatch form and try again.")
            return redirect(reverse("projects_web:detail", args=[pk]))
        data = form.cleaned_data
        try:
            inventory_services.stock_out(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=request.user, project_id=pk, reason_code="deep_clean", comment=data["comment"],
            )
            services.mark_active(pk)
            messages.success(request, f"{data['quantity']} {data['product'].name} dispatched to project.")
        except (InsufficientStockError, StockLevelChangedError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("projects_web:detail", args=[pk]))


class ProjectReturnView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ProjectReturnForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the return form and try again.")
            return redirect(reverse("projects_web:detail", args=[pk]))
        data = form.cleaned_data
        try:
            inventory_services.return_stock(
                product_id=data["product"].id, warehouse_id=data["warehouse"].id, quantity=data["quantity"],
                performed_by=request.user, project_id=pk, reason_code="deep_clean_return", comment=data["comment"],
            )
            messages.success(request, f"{data['quantity']} {data['product'].name} returned from project.")
        except StockLevelChangedError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("projects_web:detail", args=[pk]))


class ProjectEquipmentAssignView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ProjectEquipmentAssignForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Pick an available equipment item.")
            return redirect(reverse("projects_web:detail", args=[pk]))
        data = form.cleaned_data
        try:
            equipment_services.assign(
                equipment_id=data["equipment"].id, project_id=pk, performed_by=request.user,
                comment=data["comment"], override=data["override"], override_reason=data["override_reason"],
            )
            services.mark_active(pk)
            messages.success(request, f"{data['equipment'].asset_id} assigned to project.")
        except EquipmentComplianceBlockedError as exc:
            messages.error(request, "Blocked: " + "; ".join(exc.blockers) + " -- check Override to force it.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("projects_web:detail", args=[pk]))


class ProjectEquipmentReleaseView(ProjectAccessMixin, View):
    def post(self, request, pk, equipment_id):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        try:
            equipment_services.release(equipment_id=equipment_id, performed_by=request.user, comment="Released from project")
            messages.success(request, "Equipment released from project.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("projects_web:detail", args=[pk]))


class ProjectVehicleAssignView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ProjectVehicleAssignForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Pick an available vehicle.")
            return redirect(reverse("projects_web:detail", args=[pk]))
        data = form.cleaned_data
        try:
            vehicle_services.assign(
                vehicle_id=data["vehicle"].id, project_id=pk, driver_id=data["driver"].id if data["driver"] else None,
                performed_by=request.user, comment=data["comment"], override=data["override"],
                override_reason=data["override_reason"],
            )
            services.mark_active(pk)
            messages.success(request, f"{data['vehicle'].registration} assigned to project.")
        except VehicleComplianceBlockedError as exc:
            messages.error(request, "Blocked: " + "; ".join(exc.blockers) + " -- check Override to force it.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("projects_web:detail", args=[pk]))


class ProjectVehicleReleaseView(ProjectAccessMixin, View):
    def post(self, request, pk, vehicle_id):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        try:
            vehicle_services.release(vehicle_id=vehicle_id, performed_by=request.user, comment="Released from project")
            messages.success(request, "Vehicle released from project.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("projects_web:detail", args=[pk]))


class ShiftLogCreateView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ShiftLogForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the shift log and try again.")
            return redirect(reverse("projects_web:detail", args=[pk]))
        data = form.cleaned_data
        log = services.log_shift(
            project_id=pk, work_date=data["work_date"], shift=data["shift"], start_time=data["start_time"],
            end_time=data["end_time"], employee_ids=[e.id for e in data["employees"]], logged_by=request.user,
            notes=data["notes"],
        )
        services.mark_active(pk)
        messages.success(request, f"Shift logged -- {log.employees.count()} crew, {log.hours_worked}h each.")
        return redirect(reverse("projects_web:detail", args=[pk]))


class ToolboxTalkCreateView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ToolboxTalkForm(request.POST, request.FILES)
        if not form.is_valid():
            for error in form.non_field_errors():
                messages.error(request, error)
            if not form.non_field_errors():
                messages.error(request, "Check the toolbox talk form and try again -- pick at least one attendee.")
            return redirect(reverse("projects_web:detail", args=[pk]))
        data = form.cleaned_data
        talk = services.create_toolbox_talk(
            project_id=pk, work_date=data["work_date"], topic=data["topic"], content=data["content"],
            attachment=data["attachment"], conducted_by=request.user, employee_ids=[e.id for e in data["employees"]],
            request=request,
        )
        messages.success(request, "Toolbox talk created -- a signing link has been emailed to each attendee.")
        return redirect(reverse("projects_web:toolbox-talk-detail", args=[pk, talk.pk]))


class ToolboxTalkDetailView(ProjectAccessMixin, View):
    def get(self, request, pk, talk_id):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        talk = get_object_or_404(ToolboxTalk, pk=talk_id, project=project)
        attendees = talk.attendees.select_related("employee").all()
        can_manage = _can_manage_project(request.user, project)
        sign_links = {}
        if can_manage:
            sign_links = {a.pk: services.toolbox_talk_sign_url(request, a) for a in attendees}
        return render(request, "projects/toolbox_talk_detail.html", {
            "project": project, "talk": talk, "attendees": attendees, "sign_links": sign_links,
            "can_manage": can_manage,
        })


class ToolboxTalkResendEmailView(ProjectAccessMixin, View):
    def post(self, request, pk, talk_id, attendee_id):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        attendee = get_object_or_404(
            ToolboxTalkAttendee, pk=attendee_id, toolbox_talk_id=talk_id, toolbox_talk__project=project,
        )
        sent = services.send_toolbox_talk_email(attendee, request)
        if sent:
            messages.success(request, f"Signing link re-sent to {attendee.employee.email}.")
        else:
            link = services.toolbox_talk_sign_url(request, attendee)
            messages.warning(request, f"Couldn't send the email -- share this link directly: {link}")
        return redirect(reverse("projects_web:toolbox-talk-detail", args=[pk, talk_id]))


def _save_signature(attendee, data_url):
    import base64

    from django.core.files.base import ContentFile

    if not data_url.startswith("data:image/png;base64,"):
        return False
    raw = base64.b64decode(data_url.split(",", 1)[1])
    signature_file = ContentFile(raw, name=f"attendee-{attendee.pk}.png")
    services.record_signature(attendee_id=attendee.pk, signature_file=signature_file)
    return True


class ToolboxTalkSignView(ProjectAccessMixin, View):
    """Supervisor-side fallback -- sign in person on the supervisor's own
    device. The primary flow is the emailed personal link (see
    ToolboxTalkPublicSignView) but this stays as a backup for anyone
    without email access."""

    def post(self, request, pk, talk_id, attendee_id):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        attendee = get_object_or_404(
            ToolboxTalkAttendee, pk=attendee_id, toolbox_talk_id=talk_id, toolbox_talk__project=project,
        )
        if not _save_signature(attendee, request.POST.get("signature_data", "")):
            messages.error(request, "No signature captured -- please sign before saving.")
        else:
            messages.success(request, f"{attendee.employee.full_name} signed.")
        return redirect(reverse("projects_web:toolbox-talk-detail", args=[pk, talk_id]))


class ToolboxTalkPublicSignView(View):
    """Public, tokenized signing page -- the link each attendee is emailed.
    No login required, same pattern as the employee onboarding link."""

    template_name = "projects/toolbox_talk_sign.html"

    def get(self, request, token):
        attendee = ToolboxTalkAttendee.objects.select_related("toolbox_talk__project", "employee").filter(
            sign_token=token
        ).first()
        if not attendee:
            return render(request, self.template_name, {"invalid": True})
        return render(request, self.template_name, {"attendee": attendee, "talk": attendee.toolbox_talk})

    def post(self, request, token):
        attendee = ToolboxTalkAttendee.objects.select_related("toolbox_talk__project", "employee").filter(
            sign_token=token
        ).first()
        if not attendee:
            return render(request, self.template_name, {"invalid": True})
        if attendee.is_signed:
            return render(request, self.template_name, {"attendee": attendee, "talk": attendee.toolbox_talk})
        if not _save_signature(attendee, request.POST.get("signature_data", "")):
            return render(request, self.template_name, {
                "attendee": attendee, "talk": attendee.toolbox_talk, "error": "No signature captured -- please sign before saving.",
            })
        attendee.refresh_from_db()
        return render(request, self.template_name, {"attendee": attendee, "talk": attendee.toolbox_talk, "submitted": True})


class ProjectCloseView(ProjectAccessMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(DeepCleanProject, pk=pk)
        _require_manage(request, project)
        form = ProjectCloseForm(request.POST)
        override = form.data.get("override") == "on"
        override_reason = form.data.get("override_reason", "")
        try:
            services.close_project(
                project_id=pk, performed_by=request.user, override=override, override_reason=override_reason,
            )
            messages.success(request, f"Project {project.reference} closed.")
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("blocked:"):
                messages.error(request, "Cannot close: " + msg[len("blocked:"):] + " -- check Override to force it.")
            else:
                messages.error(request, msg)
        return redirect(reverse("projects_web:detail", args=[pk]))
