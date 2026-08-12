from django.conf import settings
from django.db import models


class Announcement(models.Model):
    """A message from a supervisor/admin to a chosen set of employees,
    delivered through the existing Notification system (in-app + best-
    effort email) -- see apps.announcements.services.create_announcement.
    Read tracking reuses Notification's own is_read/read_at rather than a
    second parallel flag (see AnnouncementRecipient.notification)."""

    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def read_count(self) -> int:
        return self.recipients.filter(notification__is_read=True).count()

    @property
    def total_count(self) -> int:
        return self.recipients.count()


class AnnouncementRecipient(models.Model):
    """Who an announcement went to. Employees with a login get `user` +
    `notification` set, and "read" is that Notification's own is_read/
    read_at (single source of truth -- see Announcement docstring).
    Employees with no login can't have a Notification (it's strictly
    per-User), so they get a plain `email_sent` instead -- there's no
    login to read it *in*, so read/unread doesn't apply to them; the best
    we can show a manager is whether the email went out."""

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="recipients")
    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="announcement_receipts", null=True, blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_receipts",
        null=True, blank=True,
    )
    notification = models.ForeignKey(
        "notifications.Notification", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    email_sent = models.BooleanField(default=False, help_text="Set for no-login employees, emailed directly.")

    class Meta:
        ordering = ["employee__first_name", "employee__last_name", "user__username"]
        constraints = [
            models.UniqueConstraint(fields=["announcement", "user"], name="uniq_announcement_recipient_user"),
            models.UniqueConstraint(fields=["announcement", "employee"], name="uniq_announcement_recipient_employee"),
        ]

    def __str__(self):
        return f"{self.user or self.employee} -- {self.announcement}"

    @property
    def display_name(self) -> str:
        if self.user:
            return self.user.get_full_name() or self.user.username
        if self.employee:
            return f"{self.employee.first_name} {self.employee.last_name}"
        return "(unknown)"

    @property
    def has_login(self) -> bool:
        return self.user_id is not None

    @property
    def is_read(self) -> bool:
        return bool(self.notification and self.notification.is_read)

    @property
    def read_at(self):
        return self.notification.read_at if self.notification else None
