from django.db import models


class Warehouse(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Station(models.Model):
    """Stub entity for Module 6 (Station Management, built later). Enough
    fields to hang FKs (SiteAssignment, InventoryTransaction, Batch) off of
    now; the full module adds richer fields via an additive migration.
    """

    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
