import secrets

from django.db import models


def _generate_nfc_token() -> str:
    return secrets.token_urlsafe(18)


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

    # Unguessable token for the NFC clock-in tag left on site -- the tag
    # itself just encodes a URL containing this, no separate provisioning
    # step needed in the app beyond reading it off the station page.
    nfc_token = models.CharField(max_length=32, unique=True, default=_generate_nfc_token, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
