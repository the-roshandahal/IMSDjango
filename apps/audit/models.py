from django.conf import settings
from django.db import models

from apps.core.models import ImmutableModel


class AuditLog(ImmutableModel):
    """Append-only record of every user action, permission/role change, and
    login event across the system (SRS Section 5.14). Retained indefinitely
    at the application level (minimum 7 years per Section 6.5) — there is no
    delete path, by design.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=64)  # e.g. "user.role_changed", "auth.login_failed"
    entity_type = models.CharField(max_length=64)  # e.g. "User", "InventoryTransaction"
    entity_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.action} ({self.entity_type}:{self.entity_id})"

    @classmethod
    def log(cls, *, actor, action, entity_type, entity_id="", metadata=None, ip_address=None):
        return cls.objects.create(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata=metadata or {},
            ip_address=ip_address,
        )
