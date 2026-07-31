from decimal import Decimal

from django import forms

from apps.catalogue.models import Category, Product
from apps.warehouses.models import Warehouse


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "parent"]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name", "category", "barcode", "image", "is_hazardous", "hazard_class",
            "sds_document", "is_batch_tracked", "reorder_point", "minimum_stock_level",
            "default_storage_location",
        ]
        help_texts = {
            "reorder_point": (
                "Low-stock alert threshold for this product. Set it per product -- e.g. 2 for a "
                "chemical you rarely use, 20+ for one you go through daily."
            ),
        }


class ProductCreateForm(ProductForm):
    """Adds optional fields for recording stock the company already has on
    hand when a product is first added to IMS -- not part of the Product
    model, handled separately by the view after the product is created."""

    initial_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(is_active=True), required=False,
        label="Existing stock location",
        help_text="If this product already exists in your stores, record where it currently is.",
    )
    initial_quantity = forms.DecimalField(
        required=False, min_value=Decimal("0"), decimal_places=2, max_digits=12,
        label="Existing quantity on hand",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("initial_quantity") and not cleaned.get("initial_warehouse"):
            raise forms.ValidationError("Choose a warehouse for the existing quantity you entered.")
        return cleaned
