from datetime import datetime, timedelta

from django.conf import settings
from django.db import models


class ProjectStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"


class Shift(models.TextChoices):
    DAY = "day", "Day"
    NIGHT = "night", "Night"


class DeepCleanProject(models.Model):
    """SRS Section 5.7, scoped to station-based projects for now -- a
    standalone client-site location and a linked Client entity are
    documented future extensions (SRS Gap #14), not built this pass.

    Chemicals/equipment/vehicles dispatched here become real stock/assets
    "at" this project the same way they can be at a warehouse or station
    (see the additive `project` FK on StockLevel/InventoryTransaction and
    `current_project` on Equipment/Vehicle) -- so "remaining chemicals" and
    "still-assigned equipment" are real, queryable facts, not notes.
    """

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    station = models.ForeignKey("warehouses.Station", on_delete=models.PROTECT, related_name="deep_clean_projects")
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
    workers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="deep_clean_shifts", blank=True)
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
