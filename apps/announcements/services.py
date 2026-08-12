from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from apps.announcements.models import Announcement, AnnouncementRecipient
from apps.notifications import services as notification_services


def create_announcement(*, title, content, created_by, employees):
    """Creates the announcement and one AnnouncementRecipient per employee.
    Employees with a login get a real Notification (in-app + best-effort
    email) via the existing notification system -- "read" tracking is then
    just that Notification's own is_read/read_at, not a second state to
    keep in sync. Employees with no login have no account to notify
    in-app, so they're emailed directly instead (best-effort, same as
    every other outbound email in this codebase) -- there's nothing for
    them to "read" in the app, so they're tracked as emailed, not read/
    unread."""
    announcement = Announcement.objects.create(title=title, content=content, created_by=created_by)
    link = reverse("announcements_web:detail", args=[announcement.pk])

    recipients = []
    for employee in employees:
        if employee.user_id:
            notification = notification_services.notify(
                recipient=employee.user, type="announcement", title=title, message=content, link=link,
            )
            recipients.append(AnnouncementRecipient(
                announcement=announcement, employee=employee, user=employee.user, notification=notification,
            ))
        else:
            sent = _email_employee_directly(employee, title, content)
            recipients.append(AnnouncementRecipient(announcement=announcement, employee=employee, email_sent=sent))
    AnnouncementRecipient.objects.bulk_create(recipients)
    return announcement


def _email_employee_directly(employee, subject, message):
    """For employees with no login -- there's no Notification to piggyback
    on (it's strictly per-User), so this sends the same best-effort plain
    email the notification system would have sent, straight to the
    employee's own address on file."""
    if not employee.email:
        return False
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [employee.email], fail_silently=True)
        return True
    except Exception:
        return False
