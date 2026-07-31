import io
import uuid

import qrcode
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.equipment.models import Equipment, EquipmentLog, EquipmentStatus, TestResult


def provision_qr_code(equipment: Equipment) -> None:
    """Mirrors apps.catalogue.services.provision_codes -- called once, right
    after creation, to replace the save()-assigned placeholder."""
    equipment.qr_code_data = f"EQUIP-{equipment.pk}-{uuid.uuid4().hex[:12]}"
    img = qrcode.make(equipment.qr_code_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    equipment.qr_code_image.save(f"equipment-{equipment.pk}.png", ContentFile(buf.getvalue()), save=False)
    equipment.save(update_fields=["qr_code_data", "qr_code_image"])


class EquipmentUnavailableError(Exception):
    """Raised when an assign/maintenance transition can't proceed because
    the item isn't in the expected state -- someone else changed it first,
    or it was never available (double-booking prevention, Gap #6)."""


class ComplianceBlockedError(Exception):
    """Raised when maintenance/test-tag compliance blocks a new assignment
    and no override was given (SRS Section 5.8 business rule)."""

    def __init__(self, blockers):
        self.blockers = blockers
        super().__init__("; ".join(blockers))


def check_assigned_equipment(user) -> list[str]:
    """Reassignment-blocker hook for apps.accounts (user deactivation)."""
    items = Equipment.objects.filter(assigned_user=user).values_list("asset_id", flat=True)
    return [f"Equipment {asset_id} is still assigned to this user" for asset_id in items]


@transaction.atomic
def assign(
    *, equipment_id, performed_by, station_id=None, project_id=None, assigned_user_id=None,
    comment="", override=False, override_reason="",
):
    """Assign to a station or a deep clean project (mutually exclusive)."""
    if station_id is not None and project_id is not None:
        raise ValueError("Assign to a station or a project, not both.")
    if station_id is None and project_id is None:
        raise ValueError("Assign requires a station_id or project_id.")

    equipment = Equipment.objects.get(pk=equipment_id)
    blockers = equipment.compliance_blockers
    if blockers and not override:
        raise ComplianceBlockedError(blockers)
    if blockers and override and not override_reason:
        raise ValueError("Overriding a compliance block requires a reason.")

    updated = Equipment.objects.filter(pk=equipment_id, status=EquipmentStatus.AVAILABLE).update(
        status=EquipmentStatus.ASSIGNED, current_station_id=station_id, current_project_id=project_id,
        current_warehouse=None, assigned_user_id=assigned_user_id,
    )
    if updated == 0:
        raise EquipmentUnavailableError(
            f"Equipment {equipment.asset_id} is not available for assignment (already assigned, in "
            "maintenance, lost, or written off)."
        )

    EquipmentLog.objects.create(
        equipment_id=equipment_id, action="assigned", station_id=station_id, project_id=project_id,
        assigned_user_id=assigned_user_id,
        override_used=bool(blockers and override), comment=comment or override_reason, performed_by=performed_by,
    )
    return Equipment.objects.get(pk=equipment_id)


# Backward-compatible alias -- station-only assignment is still the common case.
def assign_to_station(*, equipment_id, station_id, assigned_user_id, performed_by, comment="", override=False, override_reason=""):
    return assign(
        equipment_id=equipment_id, station_id=station_id, assigned_user_id=assigned_user_id,
        performed_by=performed_by, comment=comment, override=override, override_reason=override_reason,
    )


@transaction.atomic
def release(*, equipment_id, performed_by, comment="", warehouse_id=None):
    updated = Equipment.objects.filter(pk=equipment_id, status=EquipmentStatus.ASSIGNED).update(
        status=EquipmentStatus.AVAILABLE, current_station=None, current_project=None, assigned_user=None,
        current_warehouse_id=warehouse_id,
    )
    if updated == 0:
        raise EquipmentUnavailableError("Equipment is not currently assigned.")
    EquipmentLog.objects.create(equipment_id=equipment_id, action="released", comment=comment, performed_by=performed_by)
    return Equipment.objects.get(pk=equipment_id)


@transaction.atomic
def start_maintenance(*, equipment_id, performed_by, comment=""):
    updated = (
        Equipment.objects.filter(pk=equipment_id)
        .exclude(status__in=[EquipmentStatus.IN_MAINTENANCE, EquipmentStatus.LOST, EquipmentStatus.WRITTEN_OFF])
        .update(status=EquipmentStatus.IN_MAINTENANCE, current_station=None, current_project=None, assigned_user=None)
    )
    if updated == 0:
        raise EquipmentUnavailableError("Equipment is already in maintenance, lost, or written off.")
    EquipmentLog.objects.create(
        equipment_id=equipment_id, action="maintenance_start", comment=comment, performed_by=performed_by
    )
    return Equipment.objects.get(pk=equipment_id)


@transaction.atomic
def end_maintenance(*, equipment_id, performed_by, comment="", warehouse_id=None):
    equipment = Equipment.objects.get(pk=equipment_id)
    updated = Equipment.objects.filter(pk=equipment_id, status=EquipmentStatus.IN_MAINTENANCE).update(
        status=EquipmentStatus.AVAILABLE,
        last_maintenance_at=timezone.now().date(),
        next_maintenance_due=equipment.compute_next_maintenance_due(),
        current_warehouse_id=warehouse_id,
    )
    if updated == 0:
        raise EquipmentUnavailableError("Equipment is not currently in maintenance.")
    EquipmentLog.objects.create(
        equipment_id=equipment_id, action="maintenance_end", comment=comment, performed_by=performed_by
    )
    return Equipment.objects.get(pk=equipment_id)


@transaction.atomic
def record_test(*, equipment_id, result, performed_by, comment="", tested_at=None):
    if result not in TestResult.values:
        raise ValueError(f"Invalid test result '{result}'.")
    equipment = Equipment.objects.get(pk=equipment_id)
    test_date = tested_at or timezone.now().date()
    equipment.last_test_date = test_date
    equipment.last_test_result = result
    equipment.last_tested_by = performed_by
    equipment.next_test_due = equipment.compute_next_test_due(test_date)
    equipment.save(update_fields=["last_test_date", "last_test_result", "last_tested_by", "next_test_due"])
    EquipmentLog.objects.create(
        equipment_id=equipment_id, action="test_recorded",
        comment=comment or f"Result: {result}", performed_by=performed_by,
    )
    return equipment


@transaction.atomic
def mark_lost(*, equipment_id, performed_by, comment=""):
    updated = (
        Equipment.objects.filter(pk=equipment_id)
        .exclude(status__in=[EquipmentStatus.LOST, EquipmentStatus.WRITTEN_OFF])
        .update(status=EquipmentStatus.LOST, current_station=None, current_project=None, current_warehouse=None, assigned_user=None)
    )
    if updated == 0:
        raise EquipmentUnavailableError("Equipment is already lost or written off.")
    EquipmentLog.objects.create(equipment_id=equipment_id, action="lost", comment=comment, performed_by=performed_by)
    return Equipment.objects.get(pk=equipment_id)


@transaction.atomic
def write_off(*, equipment_id, performed_by, comment=""):
    updated = (
        Equipment.objects.filter(pk=equipment_id)
        .exclude(status=EquipmentStatus.WRITTEN_OFF)
        .update(status=EquipmentStatus.WRITTEN_OFF, current_station=None, current_project=None, current_warehouse=None, assigned_user=None)
    )
    if updated == 0:
        raise EquipmentUnavailableError("Equipment is already written off.")
    EquipmentLog.objects.create(
        equipment_id=equipment_id, action="written_off", comment=comment, performed_by=performed_by
    )
    return Equipment.objects.get(pk=equipment_id)
