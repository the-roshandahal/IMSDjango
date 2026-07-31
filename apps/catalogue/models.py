from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """SRS Section 5.3. Archived (not deleted) products stay out of new
    transactions but remain visible for history."""

    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    barcode = models.CharField(max_length=64, unique=True, db_index=True)
    qr_code_data = models.CharField(max_length=128, unique=True, blank=True, db_index=True)
    qr_code_image = models.ImageField(upload_to="qr_codes/", blank=True)
    image = models.ImageField(upload_to="products/", blank=True)

    is_hazardous = models.BooleanField(default=False)
    hazard_class = models.CharField(max_length=64, blank=True)
    sds_document = models.FileField(upload_to="sds/", blank=True, null=True)  # placeholder until Documents module (5.16)

    is_batch_tracked = models.BooleanField(default=False)  # chemicals/consumables with expiry
    reorder_point = models.PositiveIntegerField(default=0)
    minimum_stock_level = models.PositiveIntegerField(default=0)

    default_storage_location = models.CharField(max_length=200, blank=True)  # aisle/shelf/bin reference

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["is_archived"])]

    def __str__(self):
        return self.name


class Batch(models.Model):
    """Descriptive batch/expiry metadata for batch-tracked products. The
    live on-hand balance for a batch is tracked in
    apps.inventory.models.StockLevel (single source of truth) — Batch itself
    is never mutated by stock transactions, only referenced by them.
    """

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="batches")
    warehouse = models.ForeignKey("warehouses.Warehouse", on_delete=models.PROTECT, related_name="batches")
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "warehouse", "batch_number"], name="uniq_batch_per_warehouse")
        ]
        indexes = [
            models.Index(fields=["product", "warehouse"]),
            models.Index(fields=["expiry_date"]),
        ]
        ordering = ["expiry_date"]

    def __str__(self):
        return f"{self.product} / {self.batch_number}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date <= timezone.now().date())
