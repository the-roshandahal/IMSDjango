from rest_framework import serializers

from apps.catalogue.models import Batch, Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent"]


class BatchSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Batch
        fields = ["id", "product", "warehouse", "batch_number", "expiry_date", "received_at", "is_expired"]
        read_only_fields = ["id", "received_at", "is_expired"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "name", "category", "barcode", "qr_code_data", "qr_code_image", "image",
            "is_hazardous", "hazard_class", "sds_document", "is_batch_tracked",
            "reorder_point", "minimum_stock_level", "default_storage_location",
            "is_archived", "created_at",
        ]
        read_only_fields = ["id", "qr_code_data", "qr_code_image", "is_archived", "created_at"]
