from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    LOW_STOCK = "low_stock", "Low stock"
    EXPIRY = "expiry", "Expiring stock"
    MAINTENANCE_DUE = "maintenance_due", "Maintenance due"
    VEHICLE_COMPLIANCE = "vehicle_compliance", "Vehicle compliance"
    REQUEST_OUTSTANDING = "request_outstanding", "Outstanding request"
    PO_STATUS = "po_status", "Purchase order"
    STOCKTAKE_OVERDUE = "stocktake_overdue", "Stock count overdue"
    HAZARD_REPORTED = "hazard_reported", "Hazard/incident reported"


class Notification(models.Model):
    """SRS Section 5.13. In-app + best-effort email; SMS is an optional
    channel per the SRS and out of scope here (needs a 3rd-party gateway).
    `dedupe_key` lets a repeated trigger (e.g. stock staying low across
    several stock_out calls, or a daily periodic check re-running) skip
    creating a duplicate alert -- see apps.notifications.services.notify."""

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=24, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    dedupe_key = models.CharField(max_length=140, blank=True, db_index=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"
