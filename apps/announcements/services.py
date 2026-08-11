from django.urls import reverse

from apps.announcements.models import Announcement, AnnouncementRecipient
from apps.notifications import services as notification_services


def create_announcement(*, title, content, created_by, employees):
    """Creates the announcement, one AnnouncementRecipient per employee
    with a login, and a real Notification for each (in-app + best-effort
    email) via the existing notification system -- "read" tracking is then
    just that Notification's own is_read/read_at, not a second state to
    keep in sync. Employees with no login are silently skipped -- there's
    no account to notify."""
    announcement = Announcement.objects.create(title=title, content=content, created_by=created_by)
    link = reverse("announcements_web:detail", args=[announcement.pk])

    recipients = []
    for employee in employees:
        if not employee.user_id:
            continue
        notification = notification_services.notify(
            recipient=employee.user, type="announcement", title=title, message=content, link=link,
        )
        recipients.append(AnnouncementRecipient(announcement=announcement, user=employee.user, notification=notification))
    AnnouncementRecipient.objects.bulk_create(recipients)
    return announcement
