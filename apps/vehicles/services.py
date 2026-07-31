from django.db import transaction

from apps.vehicles.models import CostType, Vehicle, VehicleCostLog, VehicleLog, VehicleStatus


class VehicleUnavailableError(Exception):
    pass


class ComplianceBlockedError(Exception):
    def __init__(self, blockers):
        self.blockers = blockers
        super().__init__("; ".join(blockers))


def check_assigned_vehicles(user) -> list[str]:
    """Reassignment-blocker hook for apps.accounts (user deactivation)."""
    items = Vehicle.objects.filter(assigned_driver=user).values_list("registration", flat=True)
    return [f"Vehicle {reg} is still assigned to this user as driver" for reg in items]


@transaction.atomic
def assign(
    *, vehicle_id, performed_by, station_id=None, project_id=None, driver_id=None,
    comment="", override=False, override_reason="",
):
    """Assign to a station or a deep clean project (mutually exclusive)."""
    if station_id is not None and project_id is not None:
        raise ValueError("Assign to a station or a project, not both.")
    if station_id is None and project_id is None:
        raise ValueError("Assign requires a station_id or project_id.")

    vehicle = Vehicle.objects.get(pk=vehicle_id)
    blockers = vehicle.compliance_blockers
    if blockers and not override:
        raise ComplianceBlockedError(blockers)
    if blockers and override and not override_reason:
        raise ValueError("Overriding a compliance block requires a reason.")

    updated = Vehicle.objects.filter(pk=vehicle_id, status=VehicleStatus.AVAILABLE).update(
        status=VehicleStatus.ASSIGNED, current_station_id=station_id, current_project_id=project_id,
        assigned_driver_id=driver_id,
    )
    if updated == 0:
        raise VehicleUnavailableError(
            f"Vehicle {vehicle.registration} is not available for assignment (already assigned, in "
            "maintenance, or written off)."
        )
    VehicleLog.objects.create(
        vehicle_id=vehicle_id, action="assigned", station_id=station_id, project_id=project_id, driver_id=driver_id,
        override_used=bool(blockers and override), comment=comment or override_reason, performed_by=performed_by,
    )
    return Vehicle.objects.get(pk=vehicle_id)


# Backward-compatible alias -- station-only assignment is still the common case.
def assign_to_station(*, vehicle_id, station_id, driver_id, performed_by, comment="", override=False, override_reason=""):
    return assign(
        vehicle_id=vehicle_id, station_id=station_id, driver_id=driver_id, performed_by=performed_by,
        comment=comment, override=override, override_reason=override_reason,
    )


@transaction.atomic
def release(*, vehicle_id, performed_by, comment=""):
    updated = Vehicle.objects.filter(pk=vehicle_id, status=VehicleStatus.ASSIGNED).update(
        status=VehicleStatus.AVAILABLE, current_station=None, current_project=None, assigned_driver=None,
    )
    if updated == 0:
        raise VehicleUnavailableError("Vehicle is not currently assigned.")
    VehicleLog.objects.create(vehicle_id=vehicle_id, action="released", comment=comment, performed_by=performed_by)
    return Vehicle.objects.get(pk=vehicle_id)


@transaction.atomic
def start_maintenance(*, vehicle_id, performed_by, comment=""):
    updated = (
        Vehicle.objects.filter(pk=vehicle_id)
        .exclude(status__in=[VehicleStatus.IN_MAINTENANCE, VehicleStatus.WRITTEN_OFF])
        .update(status=VehicleStatus.IN_MAINTENANCE, current_station=None, current_project=None, assigned_driver=None)
    )
    if updated == 0:
        raise VehicleUnavailableError("Vehicle is already in maintenance or written off.")
    VehicleLog.objects.create(
        vehicle_id=vehicle_id, action="maintenance_start", comment=comment, performed_by=performed_by
    )
    return Vehicle.objects.get(pk=vehicle_id)


@transaction.atomic
def end_maintenance(*, vehicle_id, performed_by, comment="", next_service_due_date=None):
    updated = Vehicle.objects.filter(pk=vehicle_id, status=VehicleStatus.IN_MAINTENANCE).update(
        status=VehicleStatus.AVAILABLE,
        **({"service_due_date": next_service_due_date} if next_service_due_date else {}),
    )
    if updated == 0:
        raise VehicleUnavailableError("Vehicle is not currently in maintenance.")
    VehicleLog.objects.create(
        vehicle_id=vehicle_id, action="maintenance_end", comment=comment, performed_by=performed_by
    )
    return Vehicle.objects.get(pk=vehicle_id)


@transaction.atomic
def write_off(*, vehicle_id, performed_by, comment=""):
    updated = (
        Vehicle.objects.filter(pk=vehicle_id).exclude(status=VehicleStatus.WRITTEN_OFF)
        .update(status=VehicleStatus.WRITTEN_OFF, current_station=None, current_project=None, assigned_driver=None)
    )
    if updated == 0:
        raise VehicleUnavailableError("Vehicle is already written off.")
    VehicleLog.objects.create(vehicle_id=vehicle_id, action="written_off", comment=comment, performed_by=performed_by)
    return Vehicle.objects.get(pk=vehicle_id)


def log_cost(*, vehicle_id, cost_type, amount, incurred_at, recorded_by, comment="", station_id=None, project_id=None):
    if cost_type not in CostType.values:
        raise ValueError(f"Invalid cost type '{cost_type}'.")
    vehicle = Vehicle.objects.get(pk=vehicle_id)
    return VehicleCostLog.objects.create(
        vehicle=vehicle, cost_type=cost_type, amount=amount, incurred_at=incurred_at,
        station_id=station_id if station_id is not None else vehicle.current_station_id,
        project_id=project_id if project_id is not None else vehicle.current_project_id,
        comment=comment, recorded_by=recorded_by,
    )
