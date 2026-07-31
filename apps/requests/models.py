from django.conf import settings
from django.db import models


class StockRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    PARTIALLY_FULFILLED = "partially_fulfilled", "Partially Fulfilled"
    FULFILLED = "fulfilled", "Fulfilled"


class StockRequest(models.Model):
    """Station replenishment request routed to a warehouse for approval and
    dispatch (SRS Section 5.6, Gap #2). Distinct from Purchase Requests
    (future module) which route to suppliers, not warehouses."""

    station = models.ForeignKey("warehouses.Station", on_delete=models.PROTECT, related_name="stock_requests")
    warehouse = models.ForeignKey("warehouses.Warehouse", on_delete=models.PROTECT, related_name="stock_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=24, choices=StockRequestStatus.choices, default=StockRequestStatus.PENDING)
    rejection_reason = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["status", "warehouse"]), models.Index(fields=["status", "station"])]

    def __str__(self):
        return f"Request #{self.pk} ({self.station} -> {self.warehouse}) [{self.status}]"


class StockRequestLine(models.Model):
    request = models.ForeignKey(StockRequest, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT, related_name="+")
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_dispatched = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["request", "product"], name="uniq_stock_request_line_product")
        ]

    @property
    def is_fully_dispatched(self) -> bool:
        return self.quantity_dispatched >= self.quantity_requested

    def __str__(self):
        return f"{self.request} / {self.product} x{self.quantity_requested}"
