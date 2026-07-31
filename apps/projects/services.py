from django.db import transaction
from django.utils import timezone

from apps.projects.models import DeepCleanProject, ProjectStatus, ShiftLog


def check_active_project_supervision(user) -> list[str]:
    """Reassignment-blocker hook for apps.accounts (user deactivation)."""
    refs = DeepCleanProject.objects.filter(supervisor=user).exclude(status=ProjectStatus.COMPLETED).values_list(
        "reference", flat=True
    )
    return [f"Deep clean project {ref} is still supervised by this user" for ref in refs]


def create_project(*, reference, name, station_id, supervisor_id, start_date, end_date, created_by):
    return DeepCleanProject.objects.create(
        reference=reference, name=name, station_id=station_id, supervisor_id=supervisor_id,
        start_date=start_date, end_date=end_date, created_by=created_by,
    )


def mark_active(project_id):
    """First real activity on a planned project flips it to active."""
    DeepCleanProject.objects.filter(pk=project_id, status=ProjectStatus.PLANNED).update(
        status=ProjectStatus.ACTIVE
    )


def outstanding_assets(project: DeepCleanProject) -> list[str]:
    """Reusable assets (equipment/vehicles) still checked out to this
    project -- SRS Section 5.7: "A project stays open until every issued
    reusable asset is returned or formally written off." Remaining
    chemical stock is reported separately (see project detail view) but
    doesn't hard-block close -- consumables get used up, not "returned",
    as a matter of course."""
    from apps.equipment.models import Equipment
    from apps.vehicles.models import Vehicle

    blockers = []
    for asset_id in Equipment.objects.filter(current_project=project).values_list("asset_id", flat=True):
        blockers.append(f"Equipment {asset_id} is still assigned to this project")
    for reg in Vehicle.objects.filter(current_project=project).values_list("registration", flat=True):
        blockers.append(f"Vehicle {reg} is still assigned to this project")
    return blockers


@transaction.atomic
def close_project(*, project_id, performed_by, override=False, override_reason=""):
    project = DeepCleanProject.objects.get(pk=project_id)
    blockers = outstanding_assets(project)
    if blockers and not override:
        raise ValueError("blocked:" + "; ".join(blockers))
    if blockers and override and not override_reason:
        raise ValueError("Overriding outstanding assets at close requires a reason.")

    project.status = ProjectStatus.COMPLETED
    project.closed_at = timezone.now()
    project.closed_by = performed_by
    if blockers and override:
        project.close_override_reason = override_reason
    project.save(update_fields=["status", "closed_at", "closed_by", "close_override_reason"])
    return project


def log_shift(*, project_id, work_date, shift, start_time, end_time, worker_ids, logged_by, notes=""):
    log = ShiftLog.objects.create(
        project_id=project_id, work_date=work_date, shift=shift, start_time=start_time, end_time=end_time,
        logged_by=logged_by, notes=notes,
    )
    if worker_ids:
        log.workers.set(worker_ids)
    return log
