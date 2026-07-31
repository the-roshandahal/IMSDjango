from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import InventoryTransaction, Stocktake, StocktakeLine, Transfer


class StockInSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    reason_code = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class StockOutSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    station_id = serializers.IntegerField(required=False, allow_null=True)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    override_fefo = serializers.BooleanField(required=False, default=False)
    reason_code = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class TransferInitiateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    source_warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    dest_warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    dest_station_id = serializers.IntegerField(required=False, allow_null=True)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    reason_code = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("dest_warehouse_id") and not attrs.get("dest_station_id"):
            raise serializers.ValidationError("Provide dest_warehouse_id or dest_station_id.")
        return attrs


class AdjustmentSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity_delta = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason_code = serializers.CharField()
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ReturnSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    station_id = serializers.IntegerField(required=False, allow_null=True)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    reason_code = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class StationUsageSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    station_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class DamagedSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    photo = serializers.ImageField(required=False, allow_null=True)


class LostSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ExpiredSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    batch_id = serializers.IntegerField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class TransferConfirmSerializer(serializers.Serializer):
    pass  # transfer id comes from the URL; confirmed_by is request.user


class InventoryTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTransaction
        fields = [
            "id", "type", "product", "batch", "quantity", "source_warehouse", "dest_warehouse",
            "station", "reason_code", "comment", "reversal_of", "performed_by", "approved_by",
            "photo", "timestamp",
        ]
        read_only_fields = fields


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = [
            "id", "product", "quantity", "source_warehouse", "dest_warehouse", "dest_station",
            "status", "debit_txn", "credit_txn", "initiated_by", "confirmed_by", "created_at", "confirmed_at",
        ]
        read_only_fields = fields


class StocktakeLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    counted_quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class StocktakeCreateSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField()
    lines = StocktakeLineInputSerializer(many=True)


class StocktakeLineSerializer(serializers.ModelSerializer):
    variance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = StocktakeLine
        fields = ["id", "product", "batch", "system_quantity", "counted_quantity", "variance"]
        read_only_fields = fields


class StocktakeSerializer(serializers.ModelSerializer):
    lines = StocktakeLineSerializer(many=True, read_only=True)

    class Meta:
        model = Stocktake
        fields = ["id", "warehouse", "started_by", "started_at", "completed_at", "status", "lines"]
        read_only_fields = fields
