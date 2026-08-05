from django.conf import settings
from django.db import models
from django.utils import timezone


def operating_date_for(duty_sheet, at=None):
    """Which calendar date a duty sheet's activity belongs to right now.
    For a same-day duty sheet this is just today. For an overnight one
    (e.g. 10pm-6am), the early-morning portion (before its end_time) still
    belongs to the date the shift started on -- otherwise a night shift
    would silently split into two unrelated days at midnight, and a second
    employee could "pick" it again after 12am thinking it's unclaimed."""
    at = at or timezone.now()
    if duty_sheet.is_overnight and at.time() < duty_sheet.end_time:
        return at.date() - timezone.timedelta(days=1)
    return at.date()


class DutySheet(models.Model):
    """A fixed, standing checklist at a station -- e.g. "6am-2pm Platform"
    or "6am-2pm Concourse". Two duty sheets can share the same time window
    (parallel areas of the same shift); the times here are informational
    (shown to help an employee pick the right one, used to suggest a
    default) rather than an exclusive slot. Created once from the station
    page and reused every day -- there is deliberately no per-date or
    per-employee copy of this; only DutySheetTask completion is per-date
    (see TaskCompletion)."""

    station = models.ForeignKey("warehouses.Station", on_delete=models.CASCADE, related_name="duty_sheets")
    name = models.CharField(max_length=100, help_text="e.g. 6am-2pm Platform")
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["station_id", "order", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["station", "name"], name="uniq_duty_sheet_name"),
        ]

    def __str__(self):
        return f"{self.station.name} -- {self.name} ({self.start_time:%H:%M}-{self.end_time:%H:%M})"

    @property
    def is_overnight(self) -> bool:
        return self.end_time <= self.start_time


class DutySheetTask(models.Model):
    """One standing item on a duty sheet's checklist -- permanent, not tied
    to a date. `is_active` lets a supervisor retire an item without losing
    its completion history (see TaskCompletion)."""

    duty_sheet = models.ForeignKey(DutySheet, on_delete=models.CASCADE, related_name="tasks")
    description = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.description


class TaskCompletion(models.Model):
    """Whether a given DutySheetTask was done on a given date -- this is
    where "daily" state actually lives, kept separate from the permanent
    task definition above. A row only exists once someone has interacted
    with the task that day; no row for (task, date) means "not done yet",
    same as an explicit is_completed=False row. `completed_by` may be a
    different employee than whoever normally works this duty sheet -- a
    later shift picking up something the earlier one left undone."""

    task = models.ForeignKey(DutySheetTask, on_delete=models.CASCADE, related_name="completions")
    date = models.DateField()

    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        "employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_during_clock_event = models.ForeignKey(
        "ClockEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_tasks"
    )
    notes = models.TextField(blank=True, help_text="e.g. why it couldn't be completed")

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["task", "date"], name="uniq_task_completion_per_date"),
        ]

    def __str__(self):
        return f"{self.task} -- {self.date}"


class DutySheetAssignment(models.Model):
    """Which employee has claimed a duty sheet for a given date -- either
    by picking it themself at clock-in (assigned_by = their own account) or
    by a supervisor assigning it ahead of time. One employee per duty sheet
    per date (the unique constraint below); this is what makes an
    already-claimed duty sheet stop showing up for anyone else to pick."""

    duty_sheet = models.ForeignKey(DutySheet, on_delete=models.CASCADE, related_name="assignments")
    date = models.DateField()
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="duty_sheet_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["duty_sheet", "date"], name="uniq_duty_sheet_assignment_per_date"),
        ]

    def __str__(self):
        return f"{self.duty_sheet.name} -- {self.date} -- {self.employee.full_name}"


class ClockEvent(models.Model):
    class Method(models.TextChoices):
        WEB = "web", "Web"
        NFC = "nfc", "NFC tag"

    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="clock_events")
    station = models.ForeignKey("warehouses.Station", on_delete=models.PROTECT, related_name="clock_events")
    duty_sheet = models.ForeignKey(DutySheet, on_delete=models.PROTECT, related_name="clock_events")

    clock_in_at = models.DateTimeField(auto_now_add=True)
    clock_out_at = models.DateTimeField(null=True, blank=True)
    clock_in_method = models.CharField(max_length=8, choices=Method.choices, default=Method.WEB)
    clock_out_method = models.CharField(max_length=8, choices=Method.choices, blank=True)

    class Meta:
        ordering = ["-clock_in_at"]
        constraints = [
            # A DB-level guarantee nobody can clock in twice without
            # clocking out first, regardless of which view/path they used.
            models.UniqueConstraint(
                fields=["employee"], condition=models.Q(clock_out_at__isnull=True),
                name="uniq_open_clock_event_per_employee",
            ),
        ]

    def __str__(self):
        return f"{self.employee.full_name} @ {self.station.name} ({self.clock_in_at:%d %b %H:%M})"

    @property
    def is_open(self) -> bool:
        return self.clock_out_at is None

    @property
    def shift_date(self):
        """Which duty-sheet date this session belongs to, pinned to the
        moment of clock-in -- an overnight shift stays on one date even
        after the clock rolls past midnight while it's still open."""
        return operating_date_for(self.duty_sheet, at=self.clock_in_at)

    @property
    def hours_worked(self):
        if not self.clock_out_at:
            return None
        delta = self.clock_out_at - self.clock_in_at
        return round(delta.total_seconds() / 3600, 2)
