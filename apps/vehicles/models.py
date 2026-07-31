from django.conf import settings
from django.db import models
from django.utils import timezone


class VehicleStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    ASSIGNED = "assigned", "Assigned"
    IN_MAINTENANCE = "in_maintenance", "In Maintenance"
    WRITTEN_OFF = "written_off", "Written Off"


class CostType(models.TextChoices):
    FUEL = "fuel", "Fuel"
    TOLL = "toll", "Toll"
    REPAIR = "repair", "Repair"
    OTHER = "other", "Other"


class Vehicle(models.Model):
    """SRS Section 5.9. `current_project` mirrors `current_station` -- a
    vehicle can be checked out to a deep clean project the same way it can
    be checked out to a station; running cost entries record whichever the
    vehicle was at when the cost was incurred."""

    registration = models.CharField(max_length=32, unique=True, db_index=True)
    make_model = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=20, choices=VehicleStatus.choices, default=VehicleStatus.AVAILABLE)
    current_station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.PROTECT, related_name="vehicles"
    )
    current_project = models.ForeignKey(
        "projects.DeepCleanProject", null=True, blank=True, on_delete=models.PROTECT, related_name="vehicles"
    )
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_vehicles"
    )

    service_due_date = models.DateField(null=True, blank=True, db_index=True)
    insurance_expiry = models.DateField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registration"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return self.registration

    @property
    def is_service_due(self) -> bool:
        return bool(self.service_due_date and self.service_due_date <= timezone.now().date())

    @property
    def is_insurance_expired(self) -> bool:
        return bool(self.insurance_expiry and self.insurance_expiry <= timezone.now().date())

    @property
    def compliance_blockers(self) -> list[str]:
        blockers = []
        if self.is_service_due:
            blockers.append(f"Service overdue since {self.service_due_date}")
        if self.is_insurance_expired:
            blockers.append(f"Insurance expired {self.insurance_expiry}")
        return blockers


class VehicleLog(models.Model):
    ACTION_CHOICES = [
        ("assigned", "Assigned"),
        ("released", "Released"),
        ("maintenance_start", "Maintenance Started"),
        ("maintenance_end", "Maintenance Completed"),
        ("written_off", "Written Off"),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=24, choices=ACTION_CHOICES)
    station = models.ForeignKey("warehouses.Station", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    project = models.ForeignKey(
        "projects.DeepCleanProject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    override_used = models.BooleanField(default=False)
    comment = models.TextField(blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.vehicle} {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"


class VehicleCostLog(models.Model):
    """Running cost log: fuel, tolls, repairs (SRS Section 5.9)."""

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="cost_logs")
    cost_type = models.CharField(max_length=10, choices=CostType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    incurred_at = models.DateField()
    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Where the vehicle was assigned at the time of the cost.",
    )
    project = models.ForeignKey(
        "projects.DeepCleanProject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Deep clean project the vehicle was assigned to at the time of the cost.",
    )
    comment = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-incurred_at"]
        indexes = [models.Index(fields=["vehicle", "incurred_at"])]

    def __str__(self):
        return f"{self.vehicle} {self.cost_type} {self.amount} on {self.incurred_at}"
