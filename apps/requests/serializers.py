from decimal import Decimal

from rest_framework import serializers

from apps.requests.models import StockRequest, StockRequestLine


class StockRequestLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class StockRequestCreateSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField()
    lines = StockRequestLineInputSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("Provide at least one line.")
        return value


class StockRequestLineSerializer(serializers.ModelSerializer):
    is_fully_dispatched = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockRequestLine
        fields = ["id", "product", "quantity_requested", "quantity_dispatched", "is_fully_dispatched"]
        read_only_fields = fields


class StockRequestSerializer(serializers.ModelSerializer):
    lines = StockRequestLineSerializer(many=True, read_only=True)

    class Meta:
        model = StockRequest
        fields = [
            "id", "station", "warehouse", "requested_by", "approved_by", "status",
            "rejection_reason", "requested_at", "decided_at", "lines",
        ]
        read_only_fields = fields


class StockRequestRejectSerializer(serializers.Serializer):
    reason = serializers.CharField()
