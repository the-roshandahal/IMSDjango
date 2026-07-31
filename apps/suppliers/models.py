from django.db import models

from apps.catalogue.models import Product


class Supplier(models.Model):
    """SRS Section 5.10. Purchase history and delivery/quality performance
    indicators are deferred until the Purchase Order module (5.11) exists
    to generate that data -- nothing to report on yet."""

    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierProduct(models.Model):
    """A product a supplier can provide, with that supplier's price for it."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="supplier_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="supplier_products")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    supplier_sku = models.CharField(max_length=64, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    is_preferred = models.BooleanField(default=False, help_text="Preferred supplier for this product.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["supplier", "product"], name="uniq_supplier_product"),
        ]
        ordering = ["product__name"]

    def __str__(self):
        return f"{self.product.name} @ {self.supplier.name}: {self.unit_price}"
