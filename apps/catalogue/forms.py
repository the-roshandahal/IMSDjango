from django import forms

from apps.catalogue.models import Category, Product


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
