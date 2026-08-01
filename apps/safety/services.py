from django.urls import reverse
from django.utils import timezone

from apps.safety.models import HazardReport, HazardStatus


def create_hazard_report(*, reported_by, station=None, project=None, **fields):
    report = HazardReport.objects.create(reported_by=reported_by, station=station, project=project, **fields)
    _notify_new_report(report)
    return report


def resolve_hazard_report(*, report, resolved_by, corrective_action):
    report.corrective_action = corrective_action
    report.resolved_by = resolved_by
    report.resolved_at = timezone.now()
    report.status = HazardStatus.CLOSED
    report.save(update_fields=["corrective_action", "resolved_by", "resolved_at", "status"])
    return report


def _recipients_for(report):
    from apps.notifications.services import admins_and_supervisors, station_recipients

    if report.station_id:
        return list(station_recipients(report.station_id))

    recipients = {u.pk: u for u in admins_and_supervisors()}
    supervisor = report.project.supervisor
    if supervisor.is_active:
        recipients[supervisor.pk] = supervisor
    return list(recipients.values())


def _notify_new_report(report):
    from apps.notifications.services import notify_users

    reporter_name = report.reported_by.get_full_name() or report.reported_by.username
    title = f"{report.get_report_type_display()} reported ({report.get_severity_display()}): {report.title}"
    message = f"{reporter_name} reported this at {report.site}.\n\n{report.description}"
    link = reverse("safety_web:detail", args=[report.pk])
    notify_users(
        _recipients_for(report), type="hazard_reported", title=title, message=message, link=link,
    )
