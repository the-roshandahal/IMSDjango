from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, has_capability
from apps.equipment import services
from apps.equipment.forms import (
    EquipmentAssignForm,
    EquipmentForm,
    EquipmentMaintenanceForm,
    EquipmentReleaseForm,
    EquipmentTestForm,
    TestTagForm,
)
from apps.equipment.models import Equipment, TestTag
from apps.equipment.services import ComplianceBlockedError, EquipmentUnavailableError


def _can_manage_fleet(user) -> bool:
    return has_capability(user, "equipment.manage") or has_capability(user, "equipment.assign")


class EquipmentListView(CapabilityRequiredMixin, ListView):
    capability = "equipment.view_own"
    model = Equipment
    template_name = "equipment/equipment_list.html"
    context_object_name = "items"
    paginate_by = 30

    def get_queryset(self):
        qs = Equipment.objects.select_related("current_warehouse", "current_station", "current_project", "assigned_user").order_by("asset_id")
        if _can_manage_fleet(self.request.user):
            return qs
        return qs.filter(assigned_user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_fleet"] = _can_manage_fleet(self.request.user)
        return ctx


class EquipmentDetailView(CapabilityRequiredMixin, DetailView):
    capability = "equipment.view_own"
    model = Equipment
    template_name = "equipment/equipment_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        qs = Equipment.objects.select_related("current_warehouse", "current_station", "current_project", "assigned_user")
        if _can_manage_fleet(self.request.user):
            return qs
        return qs.filter(assigned_user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_fleet"] = _can_manage_fleet(self.request.user)
        ctx["logs"] = self.object.logs.select_related("station", "assigned_user", "performed_by")[:20]
        ctx["assign_form"] = EquipmentAssignForm()
        ctx["release_form"] = EquipmentReleaseForm()
        ctx["maintenance_form"] = EquipmentMaintenanceForm()
        ctx["test_form"] = EquipmentTestForm()

        from apps.documents.services import documents_for

        ctx["documents"] = documents_for(self.object)
        ctx["can_manage_documents"] = has_capability(self.request.user, "equipment.assign")
        ctx["document_model_key"] = "equipment.equipment"
        ctx["document_object_id"] = self.object.pk
        return ctx


class EquipmentCreateView(CapabilityRequiredMixin, CreateView):
    capability = "equipment.manage"
    model = Equipment
    form_class = EquipmentForm
    template_name = "equipment/equipment_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        services.provision_qr_code(self.object)
        messages.success(self.request, f"{self.object.asset_id} created.")
        return response

    def get_success_url(self):
        return reverse("equipment_web:detail", args=[self.object.pk])


class EquipmentUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "equipment.manage"
    model = Equipment
    form_class = EquipmentForm
    template_name = "equipment/equipment_form.html"

    def get_success_url(self):
        return reverse("equipment_web:detail", args=[self.object.pk])


class EquipmentAssignView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        form = EquipmentAssignForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the assignment form and try again.")
            return redirect(reverse("equipment_web:detail", args=[pk]))
        data = form.cleaned_data
        try:
            services.assign_to_station(
                equipment_id=pk, station_id=data["station"].id,
                assigned_user_id=data["assigned_user"].id if data["assigned_user"] else None,
                performed_by=request.user, comment=data["comment"],
                override=data["override"], override_reason=data["override_reason"],
            )
            messages.success(request, "Equipment assigned.")
        except ComplianceBlockedError as exc:
            messages.error(request, "Blocked: " + "; ".join(exc.blockers) + " -- check Override to force it.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("equipment_web:detail", args=[pk]))


class EquipmentReleaseView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        form = EquipmentReleaseForm(request.POST)
        comment = form.data.get("comment", "") if form.is_valid() else ""
        try:
            services.release(equipment_id=pk, performed_by=request.user, comment=comment)
            messages.success(request, "Equipment released.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("equipment_web:detail", args=[pk]))


class EquipmentMaintenanceStartView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.start_maintenance(equipment_id=pk, performed_by=request.user, comment=comment)
            messages.success(request, "Marked as in maintenance.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("equipment_web:detail", args=[pk]))


class EquipmentMaintenanceEndView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.end_maintenance(equipment_id=pk, performed_by=request.user, comment=comment)
            messages.success(request, "Maintenance completed, equipment available again.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("equipment_web:detail", args=[pk]))


class EquipmentTestView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        form = EquipmentTestForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Pick a valid test result.")
            return redirect(reverse("equipment_web:detail", args=[pk]))
        data = form.cleaned_data
        services.record_test(equipment_id=pk, result=data["result"], performed_by=request.user, comment=data["comment"])
        messages.success(request, "Test result recorded.")
        return redirect(reverse("equipment_web:detail", args=[pk]))


class EquipmentLostView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.mark_lost(equipment_id=pk, performed_by=request.user, comment=comment)
            messages.warning(request, "Equipment marked lost.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("equipment_web:detail", args=[pk]))


class EquipmentWriteOffView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.write_off(equipment_id=pk, performed_by=request.user, comment=comment)
            messages.warning(request, "Equipment written off.")
        except EquipmentUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("equipment_web:detail", args=[pk]))


# ---------------------------------------------------------------------
# Test tag register -- a lightweight compliance log, separate from the
# Equipment fleet-asset model (see TestTag docstring).
# ---------------------------------------------------------------------

class TestTagListView(CapabilityRequiredMixin, ListView):
    capability = "equipment.view_own"
    model = TestTag
    template_name = "equipment/test_tag_list.html"
    context_object_name = "tags"
    paginate_by = 50

    def get_queryset(self):
        qs = TestTag.objects.select_related("station", "warehouse", "tested_by")
        user = self.request.user
        if user.role not in SITE_SCOPE_EXEMPT_ROLES and not _can_manage_fleet(user):
            station_ids = list(assigned_site_ids(user, "station"))
            warehouse_ids = list(assigned_site_ids(user, "warehouse"))
            qs = qs.filter(Q(station_id__in=station_ids) | Q(warehouse_id__in=warehouse_ids))

        status = self.request.GET.get("status")
        today = timezone.now().date()
        if status == "expired":
            qs = qs.filter(expiry_date__lte=today)
        elif status == "expiring":
            qs = qs.filter(
                expiry_date__gt=today, expiry_date__lte=today + timezone.timedelta(days=TestTag.EXPIRY_WARNING_DAYS)
            )
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_fleet"] = _can_manage_fleet(self.request.user)
        ctx["active_status"] = self.request.GET.get("status", "")
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class TestTagCreateView(CapabilityRequiredMixin, CreateView):
    capability = "equipment.assign"
    model = TestTag
    form_class = TestTagForm
    template_name = "equipment/test_tag_form.html"

    def form_valid(self, form):
        form.instance.tested_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"Test tag for {self.object.name} recorded.")
        return response

    def get_success_url(self):
        return reverse("equipment_web:test-tag-list")


class TestTagUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "equipment.assign"
    model = TestTag
    form_class = TestTagForm
    template_name = "equipment/test_tag_form.html"

    def get_success_url(self):
        return reverse("equipment_web:test-tag-list")


class TestTagDeleteView(CapabilityRequiredMixin, View):
    capability = "equipment.assign"

    def post(self, request, pk):
        tag = get_object_or_404(TestTag, pk=pk)
        name = tag.name
        tag.delete()
        messages.success(request, f"Test tag for {name} removed.")
        return redirect(reverse("equipment_web:test-tag-list"))
