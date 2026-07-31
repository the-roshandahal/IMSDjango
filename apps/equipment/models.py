import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class EquipmentStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    ASSIGNED = "assigned", "Assigned"
    IN_MAINTENANCE = "in_maintenance", "In Maintenance"
    LOST = "lost", "Lost"
    WRITTEN_OFF = "written_off", "Written Off"


class TestResult(models.TextChoices):
    UNTESTED = "untested", "Untested"
    PASS_ = "pass", "Pass"
    FAIL = "fail", "Fail"


class Equipment(models.Model):
    """SRS Section 5.8. Current state lives directly on this row (not a
    separate assignment table) -- "only one active assignment at a time"
    (Gap #6) is then just a fact about the row, enforced the same way
    inventory concurrency is: an atomic conditional UPDATE in services.py,
    never a bare .save().

    `assigned_project` is intentionally absent -- Deep Clean Projects don't
    exist yet. Added as an additive migration when that module lands,
    exactly like InventoryTransaction.request was.
    """

    asset_id = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=100, unique=True, db_index=True)
    qr_code_data = models.CharField(max_length=128, unique=True, blank=True, db_index=True)
    qr_code_image = models.ImageField(upload_to="equipment_qr/", blank=True)

    status = models.CharField(max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.AVAILABLE)
    current_warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="equipment"
    )
    current_station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="equipment"
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_equipment"
    )

    # Maintenance (fixed interval)
    maintenance_interval_days = models.PositiveIntegerField(null=True, blank=True)
    last_maintenance_at = models.DateField(null=True, blank=True)
    next_maintenance_due = models.DateField(null=True, blank=True, db_index=True)

    # Electrical safety test tag (PAT-style)
    test_interval_days = models.PositiveIntegerField(default=365)
    last_test_date = models.DateField(null=True, blank=True)
    next_test_due = models.DateField(null=True, blank=True, db_index=True)
    last_test_result = models.CharField(max_length=10, choices=TestResult.choices, default=TestResult.UNTESTED)
    last_tested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["asset_id"]
        indexes = [models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        # Same fix as apps.catalogue.models.Product.save(): qr_code_data is
        # unique, so never leave it blank at insert time -- a placeholder
        # here avoids the collision that would otherwise block ALL future
        # equipment creation the moment any one row failed to get a real
        # code provisioned.
        if not self.qr_code_data:
            self.qr_code_data = f"PENDING-{uuid.uuid4().hex}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset_id} - {self.name}"

    @property
    def is_maintenance_due(self) -> bool:
        return bool(self.next_maintenance_due and self.next_maintenance_due <= timezone.now().date())

    @property
    def is_test_overdue(self) -> bool:
        return bool(self.next_test_due and self.next_test_due <= timezone.now().date())

    @property
    def compliance_blockers(self) -> list[str]:
        """Reasons this item should not be newly assigned. Mirrors
        apps.accounts.services.check_pending_assets in shape -- a plain
        list of human-readable strings a Supervisor can override past with
        a logged reason (SRS Section 5.8 business rule)."""
        blockers = []
        if self.is_maintenance_due:
            blockers.append(f"Maintenance overdue since {self.next_maintenance_due}")
        if self.last_test_result == TestResult.FAIL:
            blockers.append("Failed its last electrical safety test")
        if self.is_test_overdue:
            blockers.append(f"Safety test overdue since {self.next_test_due}")
        return blockers

    def compute_next_test_due(self, from_date=None):
        base = from_date or timezone.now().date()
        return base + timedelta(days=self.test_interval_days) if self.test_interval_days else None

    def compute_next_maintenance_due(self, from_date=None):
        if not self.maintenance_interval_days:
            return None
        base = from_date or timezone.now().date()
        return base + timedelta(days=self.maintenance_interval_days)


class EquipmentLog(models.Model):
    """Append-only history: every assignment, release, maintenance, and
    test event for a piece of equipment (SRS: "Service history log")."""

    ACTION_CHOICES = [
        ("assigned", "Assigned"),
        ("released", "Released"),
        ("maintenance_start", "Maintenance Started"),
        ("maintenance_end", "Maintenance Completed"),
        ("test_recorded", "Safety Test Recorded"),
        ("lost", "Marked Lost"),
        ("written_off", "Written Off"),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=24, choices=ACTION_CHOICES)
    station = models.ForeignKey("warehouses.Station", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    override_used = models.BooleanField(default=False)
    comment = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.equipment} {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"


class TestTag(models.Model):
    """Electrical safety test tag register for items too small/numerous to
    asset-track individually as Equipment (extension cords, chargers,
    power leads...) -- a station or warehouse can have many of these.
    Deliberately lighter than Equipment: no asset lifecycle/assignment,
    just what's tagged, where, and when it expires. Re-testing an item
    means adding a new row (start/expiry move forward); old rows stay as
    the tag history for that item name/location.
    """

    EXPIRY_WARNING_DAYS = 30

    name = models.CharField(max_length=200, help_text="e.g. 'Vacuum cleaner extension cord', 'Scrubber charger'")
    warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.PROTECT, related_name="test_tags"
    )
    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="test_tags"
    )
    start_date = models.DateField()
    expiry_date = models.DateField(db_index=True)
    tested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date"]
        indexes = [models.Index(fields=["expiry_date"])]

    def __str__(self):
        location = self.station or self.warehouse
        return f"{self.name} @ {location} (expires {self.expiry_date})"

    @property
    def is_expired(self) -> bool:
        return self.expiry_date <= timezone.now().date()

    @property
    def is_expiring_soon(self) -> bool:
        if self.is_expired:
            return False
        return self.expiry_date <= timezone.now().date() + timedelta(days=self.EXPIRY_WARNING_DAYS)
