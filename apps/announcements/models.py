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
    """Who an announcement went to. No read_at of its own on purpose --
    `notification` is the exact Notification row this recipient got, and
    its own is_read/read_at (already fully wired up: in-app badge, mark
    read/mark all read, best-effort email) is the single source of truth
    for whether they've read it. A second parallel "read" flag here would
    just be a sync bug waiting to happen."""

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_receipts")
    notification = models.ForeignKey(
        "notifications.Notification", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["user__first_name", "user__last_name", "user__username"]
        constraints = [
            models.UniqueConstraint(fields=["announcement", "user"], name="uniq_announcement_recipient")
        ]

    def __str__(self):
        return f"{self.user} -- {self.announcement}"

    @property
    def is_read(self) -> bool:
        return bool(self.notification and self.notification.is_read)

    @property
    def read_at(self):
        return self.notification.read_at if self.notification else None
