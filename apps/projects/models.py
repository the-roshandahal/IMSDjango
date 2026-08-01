import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models

from apps.documents.models import validate_file_extension, validate_file_size


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class ProjectStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"


class Shift(models.TextChoices):
    DAY = "day", "Day"
    NIGHT = "night", "Night"


class DeepCleanProject(models.Model):
    """SRS Section 5.7. `location` is free text (not a Station FK) --
    deep clean jobs can happen anywhere (a station, a client site, a yard),
    and requiring every location to first exist as a registered Station
    was more friction than the projects module needs. A standalone Client
    entity is a documented future extension (SRS Gap #14), not built this pass.

    Chemicals/equipment/vehicles dispatched here become real stock/assets
    "at" this project the same way they can be at a warehouse or station
    (see the additive `project` FK on StockLevel/InventoryTransaction and
    `current_project` on Equipment/Vehicle) -- so "remaining chemicals" and
    "still-assigned equipment" are real, queryable facts, not notes.
    """

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, default="", help_text="e.g. 'Auburn Station', a client site address, etc.")
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="supervised_projects"
    )
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.PLANNED)
    start_date = models.DateField()
    end_date = models.DateField(
        null=True, blank=True, help_text="Leave blank if not yet known -- projects can run a single day to several weeks."
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    close_override_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.reference} - {self.name}"

    @property
    def is_open(self) -> bool:
        return self.status != ProjectStatus.COMPLETED


class ShiftLog(models.Model):
    """One row per work session -- covers a single-day project or a
    multi-week one the same way, no separate schedule model needed. Hours
    worked is derived from start/end time (handles overnight shifts)."""

    project = models.ForeignKey(DeepCleanProject, on_delete=models.CASCADE, related_name="shift_logs")
    work_date = models.DateField()
    shift = models.CharField(max_length=10, choices=Shift.choices, default=Shift.DAY)
    start_time = models.TimeField()
    end_time = models.TimeField()
    workers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="deep_clean_shifts", blank=True,
        help_text="System-account staff on this shift (rare -- most crew are Employees below).",
    )
    employees = models.ManyToManyField(
        "employees.Employee", related_name="deep_clean_shifts", blank=True,
        help_text="The crew that actually worked this shift.",
    )
    notes = models.TextField(blank=True)
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-work_date", "-start_time"]

    def __str__(self):
        return f"{self.project} {self.work_date} ({self.get_shift_display()})"

    @property
    def hours_worked(self) -> float:
        start = datetime.combine(self.work_date, self.start_time)
        end = datetime.combine(self.work_date, self.end_time)
        if end <= start:
            end += timedelta(days=1)  # overnight shift crossing midnight
        return round((end - start).total_seconds() / 3600, 2)


class ToolboxTalk(models.Model):
    """A pre-work safety briefing (hazards + controls) for a deep clean
    project on a given day -- SRS-adjacent, requested as a company-wide
    workforce feature. Each attendee reads it (typed content and/or an
    attached document) and acknowledges with a signature via a personal
    link emailed to them -- no login required, same pattern as the
    Employee onboarding link."""

    project = models.ForeignKey(DeepCleanProject, on_delete=models.CASCADE, related_name="toolbox_talks")
    work_date = models.DateField()
    topic = models.CharField(max_length=200, help_text="e.g. 'Wet floors & chemical handling'")
    content = models.TextField(blank=True, help_text="Hazards discussed, controls, PPE required.")
    attachment = models.FileField(
        upload_to="toolbox_talks/%Y/%m/", blank=True, null=True,
        validators=[validate_file_extension, validate_file_size],
        help_text="The toolbox talk paper/form, if you have one -- attendees can view it before signing.",
    )
    conducted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-work_date", "-created_at"]

    def __str__(self):
        return f"{self.project} {self.work_date} - {self.topic}"

    @property
    def signed_count(self) -> int:
        return self.attendees.filter(signed_at__isnull=False).count()

    @property
    def total_count(self) -> int:
        return self.attendees.count()


class ToolboxTalkAttendee(models.Model):
    toolbox_talk = models.ForeignKey(ToolboxTalk, on_delete=models.CASCADE, related_name="attendees")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="toolbox_talk_attendances")
    signature = models.ImageField(upload_to="toolbox_signatures/", blank=True, null=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    sign_token = models.CharField(max_length=64, unique=True, default=_generate_token, editable=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["employee__first_name", "employee__last_name"]
        constraints = [
            models.UniqueConstraint(fields=["toolbox_talk", "employee"], name="uniq_toolboxtalk_employee")
        ]

    def __str__(self):
        return f"{self.employee} - {self.toolbox_talk}"

    @property
    def is_signed(self) -> bool:
        return self.signed_at is not None
