import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class POStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    PARTIALLY_RECEIVED = "partially_received", "Partially received"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrder(models.Model):
    """SRS Section 5.11, simplified per direct request: a Purchase Request
    and Purchase Order are the same object here -- draft is the request
    stage (still editable), sent is the order handed to the supplier
    (locked, printable). No separate approval gate."""

    reference = models.CharField(max_length=32, unique=True, blank=True, db_index=True)
    supplier = models.ForeignKey("suppliers.Supplier", on_delete=models.PROTECT, related_name="purchase_orders")
    warehouse = models.ForeignKey("warehouses.Warehouse", on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=24, choices=POStatus.choices, default=POStatus.DRAFT)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    cancel_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        # reference is unique; give every row a placeholder immediately so
        # two POs created before provisioning never collide on "" (same
        # trick as Product.qr_code_data / Equipment.qr_code_data).
        if not self.reference:
            self.reference = f"PENDING-{uuid.uuid4().hex}"
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status == POStatus.DRAFT

    @property
    def is_open_for_receiving(self) -> bool:
        return self.status in (POStatus.SENT, POStatus.PARTIALLY_RECEIVED)

    @property
    def can_cancel(self) -> bool:
        return self.status not in (POStatus.RECEIVED, POStatus.CANCELLED)

    @property
    def total_value(self) -> Decimal:
        return sum((line.line_total for line in self.lines.all()), Decimal("0"))

    def __str__(self):
        return self.reference


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT, related_name="+")
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["purchase_order", "product"], name="uniq_po_line_product"),
        ]
        ordering = ["product__name"]

    @property
    def quantity_remaining(self) -> Decimal:
        return self.quantity_ordered - self.quantity_received

    @property
    def is_fully_received(self) -> bool:
        return self.quantity_received >= self.quantity_ordered

    @property
    def line_total(self) -> Decimal:
        return self.quantity_ordered * self.unit_price

    def __str__(self):
        return f"{self.product.name} x{self.quantity_ordered}"
