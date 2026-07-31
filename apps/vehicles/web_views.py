from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import has_capability
from apps.vehicles import services
from apps.vehicles.forms import (
    VehicleAssignForm,
    VehicleCostLogForm,
    VehicleForm,
    VehicleMaintenanceEndForm,
    VehicleReleaseForm,
)
from apps.vehicles.models import Vehicle
from apps.vehicles.services import ComplianceBlockedError, VehicleUnavailableError


def _can_manage_fleet(user) -> bool:
    return has_capability(user, "vehicle.manage") or has_capability(user, "vehicle.assign")


class VehicleListView(CapabilityRequiredMixin, ListView):
    capability = "vehicle.view_own"
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"
    paginate_by = 30

    def get_queryset(self):
        qs = Vehicle.objects.select_related("current_station", "current_project", "assigned_driver").order_by("registration")
        if _can_manage_fleet(self.request.user):
            return qs
        return qs.filter(assigned_driver=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_fleet"] = _can_manage_fleet(self.request.user)
        return ctx


class VehicleDetailView(CapabilityRequiredMixin, DetailView):
    capability = "vehicle.view_own"
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"
    context_object_name = "vehicle"

    def get_queryset(self):
        qs = Vehicle.objects.select_related("current_station", "current_project", "assigned_driver")
        if _can_manage_fleet(self.request.user):
            return qs
        return qs.filter(assigned_driver=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_manage_fleet"] = _can_manage_fleet(self.request.user)
        ctx["logs"] = self.object.logs.select_related("station", "driver", "performed_by")[:20]
        ctx["costs"] = self.object.cost_logs.select_related("station", "recorded_by")[:20]
        ctx["total_cost"] = sum((c.amount for c in ctx["costs"]), start=0)
        ctx["assign_form"] = VehicleAssignForm()
        ctx["release_form"] = VehicleReleaseForm()
        ctx["maintenance_end_form"] = VehicleMaintenanceEndForm()
        ctx["cost_form"] = VehicleCostLogForm()

        from apps.documents.services import documents_for

        ctx["documents"] = documents_for(self.object)
        ctx["can_manage_documents"] = has_capability(self.request.user, "vehicle.assign")
        ctx["document_model_key"] = "vehicles.vehicle"
        ctx["document_object_id"] = self.object.pk
        return ctx


class VehicleCreateView(CapabilityRequiredMixin, CreateView):
    capability = "vehicle.manage"
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"{self.object.registration} created.")
        return response

    def get_success_url(self):
        return reverse("vehicles_web:detail", args=[self.object.pk])


class VehicleUpdateView(CapabilityRequiredMixin, UpdateView):
    capability = "vehicle.manage"
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"

    def get_success_url(self):
        return reverse("vehicles_web:detail", args=[self.object.pk])


class VehicleAssignView(CapabilityRequiredMixin, View):
    capability = "vehicle.assign"

    def post(self, request, pk):
        form = VehicleAssignForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the assignment form and try again.")
            return redirect(reverse("vehicles_web:detail", args=[pk]))
        data = form.cleaned_data
        try:
            services.assign_to_station(
                vehicle_id=pk, station_id=data["station"].id, driver_id=data["driver"].id if data["driver"] else None,
                performed_by=request.user, comment=data["comment"], override=data["override"],
                override_reason=data["override_reason"],
            )
            messages.success(request, "Vehicle assigned.")
        except ComplianceBlockedError as exc:
            messages.error(request, "Blocked: " + "; ".join(exc.blockers) + " -- check Override to force it.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("vehicles_web:detail", args=[pk]))


class VehicleReleaseView(CapabilityRequiredMixin, View):
    capability = "vehicle.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.release(vehicle_id=pk, performed_by=request.user, comment=comment)
            messages.success(request, "Vehicle released.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("vehicles_web:detail", args=[pk]))


class VehicleMaintenanceStartView(CapabilityRequiredMixin, View):
    capability = "vehicle.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.start_maintenance(vehicle_id=pk, performed_by=request.user, comment=comment)
            messages.success(request, "Marked as in maintenance.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("vehicles_web:detail", args=[pk]))


class VehicleMaintenanceEndView(CapabilityRequiredMixin, View):
    capability = "vehicle.assign"

    def post(self, request, pk):
        form = VehicleMaintenanceEndForm(request.POST)
        data = form.cleaned_data if form.is_valid() else {"comment": "", "next_service_due_date": None}
        try:
            services.end_maintenance(
                vehicle_id=pk, performed_by=request.user, comment=data["comment"],
                next_service_due_date=data.get("next_service_due_date"),
            )
            messages.success(request, "Maintenance completed, vehicle available again.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("vehicles_web:detail", args=[pk]))


class VehicleWriteOffView(CapabilityRequiredMixin, View):
    capability = "vehicle.assign"

    def post(self, request, pk):
        comment = request.POST.get("comment", "")
        try:
            services.write_off(vehicle_id=pk, performed_by=request.user, comment=comment)
            messages.warning(request, "Vehicle written off.")
        except VehicleUnavailableError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("vehicles_web:detail", args=[pk]))


class VehicleCostLogView(CapabilityRequiredMixin, View):
    capability = "vehicle.assign"

    def post(self, request, pk):
        form = VehicleCostLogForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the cost entry and try again.")
            return redirect(reverse("vehicles_web:detail", args=[pk]))
        data = form.cleaned_data
        services.log_cost(
            vehicle_id=pk, cost_type=data["cost_type"], amount=data["amount"], incurred_at=data["incurred_at"],
            recorded_by=request.user, comment=data["comment"],
        )
        messages.success(request, "Cost recorded.")
        return redirect(reverse("vehicles_web:detail", args=[pk]))
