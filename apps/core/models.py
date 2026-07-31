from django.db import models

from apps.core.exceptions import ImmutableRecordError


class ImmutableQuerySet(models.QuerySet):
    """Blocks the bulk-operation gap that instance-level save()/delete()
    overrides alone can't close: `Model.objects.filter(...).update(...)`
    and `.delete()` bypass those overrides entirely."""

    def update(self, **kwargs):
        raise ImmutableRecordError(
            f"{self.model.__name__} records are append-only; bulk update() is not permitted."
        )

    def delete(self):
        raise ImmutableRecordError(
            f"{self.model.__name__} records are append-only; bulk delete() is not permitted."
        )


class ImmutableManager(models.Manager.from_queryset(ImmutableQuerySet)):
    pass


class ImmutableModel(models.Model):
    """Base for append-only historical records (AuditLog, InventoryTransaction).

    Once a row has a pk (i.e. it has been inserted), it can never be saved or
    deleted again. Corrections happen by inserting a new compensating record,
    never by mutating history — this is a hard SRS requirement (Section 5.4,
    5.14), not just a convention, so it's enforced at the model layer.
    """

    objects = ImmutableManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableRecordError(
                f"{type(self).__name__} records cannot be modified after creation."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError(
            f"{type(self).__name__} records cannot be deleted."
        )
