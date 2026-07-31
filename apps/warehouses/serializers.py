from rest_framework import serializers

from apps.warehouses.models import Station, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "address", "capacity", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = ["id", "name", "address", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class StockSummarySerializer(serializers.Serializer):
    product_id = serializers.IntegerField(source="product__id")
    product_name = serializers.CharField(source="product__name")
    batch_id = serializers.IntegerField(source="batch__id", allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
