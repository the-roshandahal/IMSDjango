from django.conf import settings
from django.db import models


class HazardReportType(models.TextChoices):
    HAZARD = "hazard", "Hazard / unsafe condition"
    NEAR_MISS = "near_miss", "Near miss"
    INCIDENT = "incident", "Incident (injury or damage)"


class HazardSeverity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class HazardStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class HazardReport(models.Model):
    """A worker-submitted hazard, near-miss or incident report -- raised
    against exactly one site, a station or a deep clean project (same
    "exactly one" shape as Stocktake). Reporting itself carries no
    capability gate: every role can file one, because safety reporting
    is not something a permission should be able to hide -- see
    HazardReportCreateView. `hazard.manage` only governs who can
    investigate and close a report out."""

    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="hazard_reports"
    )
    project = models.ForeignKey(
        "projects.DeepCleanProject", null=True, blank=True, on_delete=models.PROTECT, related_name="hazard_reports"
    )

    report_type = models.CharField(max_length=16, choices=HazardReportType.choices, default=HazardReportType.HAZARD)
    severity = models.CharField(max_length=10, choices=HazardSeverity.choices, default=HazardSeverity.MEDIUM)
    status = models.CharField(max_length=10, choices=HazardStatus.choices, default=HazardStatus.OPEN)

    title = models.CharField(max_length=200)
    description = models.TextField()
    location_detail = models.CharField(
        max_length=200, blank=True, help_text="e.g. 'Platform 2, near the lift'"
    )
    immediate_action_taken = models.TextField(blank=True)
    injury_involved = models.BooleanField(default=False)
    photo = models.ImageField(upload_to="hazard_reports/%Y/%m/", blank=True, null=True)

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hazard_reports_filed"
    )
    reported_at = models.DateTimeField(auto_now_add=True)

    corrective_action = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-reported_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["severity"])]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(station__isnull=False, project__isnull=True)
                    | models.Q(station__isnull=True, project__isnull=False)
                ),
                name="hazard_exactly_one_site",
            )
        ]

    def __str__(self):
        return f"{self.get_report_type_display()}: {self.title} @ {self.site}"

    @property
    def site(self):
        return self.station or self.project

    @property
    def is_open(self) -> bool:
        return self.status == HazardStatus.OPEN
