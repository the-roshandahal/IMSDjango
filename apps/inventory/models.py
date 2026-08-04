from django.conf import settings
from django.db import models

from apps.core.models import ImmutableModel


class TransactionType(models.TextChoices):
    STOCK_IN = "stock_in", "Stock In"
    STOCK_OUT = "stock_out", "Stock Out"
    TRANSFER_OUT = "transfer_out", "Transfer Out"
    TRANSFER_IN = "transfer_in", "Transfer In"
    ADJUSTMENT = "adjustment", "Adjustment"
    RETURN = "return", "Return"
    DAMAGED = "damaged", "Damaged"
    LOST = "lost", "Lost"
    EXPIRED = "expired", "Expired"
    REVERSAL = "reversal", "Reversal"
    STATION_USAGE = "station_usage", "Station Usage"


class InventoryTransaction(ImmutableModel):
    """Every inventory movement, ever (SRS Section 5.4). Append-only:
    corrections are posted as a new REVERSAL transaction, never an edit.

    `request` links a dispatch back to the StockRequest it fulfilled --
    purely for traceability; the actual "must be approved" business rule
    lives in apps.requests.services (inventory stays a generic primitive
    with no awareness of approval workflows). `project` and `purchase_order`
    are the same kind of deferred field, added once apps.projects and
    apps.purchasing landed -- a deep clean project is a stock location
    exactly like a warehouse or station, and a purchase order is what a
    STOCK_IN goods receipt traces back to.
    """

    type = models.CharField(max_length=20, choices=TransactionType.choices)
    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT, related_name="transactions")
    batch = models.ForeignKey("catalogue.Batch", null=True, blank=True, on_delete=models.PROTECT, related_name="transactions")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)  # always positive; direction implied by `type`

    source_warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    dest_warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    station = models.ForeignKey("warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    project = models.ForeignKey(
        "projects.DeepCleanProject", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    request = models.ForeignKey(
        "stock_requests.StockRequest", null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions"
    )
    purchase_order = models.ForeignKey(
        "purchasing.PurchaseOrder", null=True, blank=True, on_delete=models.PROTECT, related_name="receipts"
    )

    reason_code = models.CharField(max_length=40, blank=True)
    comment = models.TextField(blank=True)

    reversal_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversals")

    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )  # sign-off, e.g. required for LOST (Section 5.4)

    photo = models.ImageField(upload_to="damaged_stock/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["product", "source_warehouse", "timestamp"]),
            models.Index(fields=["type", "timestamp"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.type} {self.quantity} {self.product} @ {self.timestamp:%Y-%m-%d %H:%M}"


class StockLevel(models.Model):
    """The single source of truth for current on-hand quantity per
    product+location(+batch). Maintained exclusively through the atomic
    conditional-update helpers in services.py -- never edited directly.
    Always re-derivable from the InventoryTransaction log if it ever drifts.
    """

    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT, related_name="stock_levels")
    warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="stock_levels"
    )
    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="stock_levels"
    )
    project = models.ForeignKey(
        "projects.DeepCleanProject", null=True, blank=True, on_delete=models.PROTECT, related_name="stock_levels"
    )
    batch = models.ForeignKey(
        "catalogue.Batch", null=True, blank=True, on_delete=models.PROTECT, related_name="stock_levels"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "warehouse", "station", "project", "batch"], name="uniq_stock_level_slot"
            )
        ]
        indexes = [
            models.Index(fields=["product", "warehouse"]),
            models.Index(fields=["product", "station"]),
            models.Index(fields=["product", "project"]),
        ]

    def __str__(self):
        location = self.warehouse or self.station or self.project
        return f"{self.product} @ {location}: {self.quantity}"


class ProductStockThreshold(models.Model):
    """A per-warehouse or per-station override of Product.reorder_point --
    a chemical that needs 50 units on hand at the main warehouse might only
    need 5 at a small station. Falls back to Product.reorder_point wherever
    no override exists for that exact (product, site) pair; see
    apps.inventory.services.effective_reorder_point."""

    product = models.ForeignKey("catalogue.Product", on_delete=models.CASCADE, related_name="stock_thresholds")
    warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.CASCADE, related_name="stock_thresholds"
    )
    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.CASCADE, related_name="stock_thresholds"
    )
    reorder_point = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(warehouse__isnull=False, station__isnull=True)
                    | models.Q(warehouse__isnull=True, station__isnull=False)
                ),
                name="threshold_exactly_one_site",
            ),
            models.UniqueConstraint(fields=["product", "warehouse"], name="uniq_threshold_product_warehouse"),
            models.UniqueConstraint(fields=["product", "station"], name="uniq_threshold_product_station"),
        ]

    @property
    def site(self):
        return self.warehouse or self.station

    def __str__(self):
        return f"{self.product} @ {self.site}: reorder at {self.reorder_point}"


class Transfer(models.Model):
    """Warehouse-to-warehouse transfers are two-phase: the debit posts
    immediately, the credit (and StockLevel increment) only on
    confirm_receipt (SRS Section 5.5)."""

    STATUS_CHOICES = [("in_transit", "In Transit"), ("completed", "Completed")]

    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT, related_name="transfers")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    source_warehouse = models.ForeignKey("warehouses.Warehouse", on_delete=models.PROTECT, related_name="+")
    dest_warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    dest_station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_transit")
    debit_txn = models.OneToOneField(InventoryTransaction, on_delete=models.PROTECT, related_name="+")
    credit_txn = models.OneToOneField(
        InventoryTransaction, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Transfer #{self.pk} {self.product} x{self.quantity} ({self.status})"


class Stocktake(models.Model):
    """A count session at exactly one site -- a warehouse (periodic full
    count) or a station (the weekly count station staff do every week,
    e.g. Sunday -- not every product is re-checked every time, so lines
    only cover what was actually counted)."""

    STATUS_CHOICES = [("open", "Open"), ("completed", "Completed")]

    warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="stocktakes"
    )
    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="stocktakes"
    )
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(warehouse__isnull=False, station__isnull=True)
                    | models.Q(warehouse__isnull=True, station__isnull=False)
                ),
                name="stocktake_exactly_one_site",
            )
        ]

    @property
    def site(self):
        return self.warehouse or self.station

    def __str__(self):
        return f"Stocktake #{self.pk} @ {self.site} ({self.status})"


class StocktakeLine(models.Model):
    stocktake = models.ForeignKey(Stocktake, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT, related_name="+")
    batch = models.ForeignKey(
        "catalogue.Batch", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    system_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["stocktake", "product", "batch"], name="uniq_stocktake_line")
        ]

    @property
    def variance(self):
        return self.counted_quantity - self.system_quantity

    def __str__(self):
        return f"{self.stocktake} / {self.product}: variance {self.variance}"
