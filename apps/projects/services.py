from django.db import transaction
from django.utils import timezone

from apps.projects.models import DeepCleanProject, ProjectStatus, ShiftLog, ToolboxTalk, ToolboxTalkAttendee


def check_active_project_supervision(user) -> list[str]:
    """Reassignment-blocker hook for apps.accounts (user deactivation)."""
    refs = DeepCleanProject.objects.filter(supervisor=user).exclude(status=ProjectStatus.COMPLETED).values_list(
        "reference", flat=True
    )
    return [f"Deep clean project {ref} is still supervised by this user" for ref in refs]


def create_project(*, reference, name, location, supervisor_id, start_date, end_date, created_by):
    return DeepCleanProject.objects.create(
        reference=reference, name=name, location=location, supervisor_id=supervisor_id,
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


def log_shift(*, project_id, work_date, shift, start_time, end_time, logged_by, worker_ids=None, employee_ids=None, notes=""):
    log = ShiftLog.objects.create(
        project_id=project_id, work_date=work_date, shift=shift, start_time=start_time, end_time=end_time,
        logged_by=logged_by, notes=notes,
    )
    if worker_ids:
        log.workers.set(worker_ids)
    if employee_ids:
        log.employees.set(employee_ids)
    return log


def create_toolbox_talk(*, work_date, topic, content, attachment, conducted_by, employee_ids, project_id=None, request=None):
    talk = ToolboxTalk.objects.create(
        project_id=project_id, work_date=work_date, topic=topic, content=content, attachment=attachment,
        conducted_by=conducted_by,
    )
    ToolboxTalkAttendee.objects.bulk_create(
        [ToolboxTalkAttendee(toolbox_talk=talk, employee_id=eid) for eid in employee_ids]
    )
    if request is not None:
        for attendee in talk.attendees.select_related("employee"):
            send_toolbox_talk_email(attendee, request)
    return talk


def toolbox_talk_sign_url(request, attendee: ToolboxTalkAttendee) -> str:
    from django.urls import reverse

    path = reverse("projects_web:toolbox-talk-sign-public", args=[attendee.sign_token])
    return request.build_absolute_uri(path)


def send_toolbox_talk_email(attendee: ToolboxTalkAttendee, request) -> bool:
    """Best-effort, same pattern as the employee onboarding invite -- the
    caller always has toolbox_talk_sign_url() to share the link manually
    (SMS/WhatsApp) regardless of whether the email actually lands."""
    from django.conf import settings
    from django.core.mail import send_mail

    if not attendee.employee.email:
        return False
    talk = attendee.toolbox_talk
    link = toolbox_talk_sign_url(request, attendee)
    subject = f"Toolbox talk -- {talk.topic}"
    where = talk.project.name if talk.project else "your team"
    message = (
        f"Hi {attendee.employee.first_name},\n\n"
        f"Please read the toolbox talk below for {where} ({talk.work_date}) and sign to confirm "
        f"you've read and understood it:\n\n{link}\n\nThanks,\nCleantech1"
    )
    attendee.email_sent_at = timezone.now()
    attendee.save(update_fields=["email_sent_at"])
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [attendee.employee.email], fail_silently=False)
        return True
    except Exception:
        return False


def record_signature(*, attendee_id, signature_file):
    attendee = ToolboxTalkAttendee.objects.select_related("toolbox_talk").get(pk=attendee_id)
    attendee.signature = signature_file
    attendee.signed_at = timezone.now()
    attendee.save(update_fields=["signature", "signed_at"])
    return attendee
