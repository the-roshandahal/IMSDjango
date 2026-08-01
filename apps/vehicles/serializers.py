from decimal import Decimal

from rest_framework import serializers

from apps.vehicles.models import CostType, Vehicle, VehicleCostLog, VehicleLocation


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id", "registration", "make_model", "status", "current_location", "assigned_driver",
            "service_due_date", "insurance_expiry", "created_at",
        ]
        read_only_fields = ["id", "status", "current_location", "assigned_driver", "created_at"]


class VehicleCostLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleCostLog
        fields = ["id", "vehicle", "cost_type", "amount", "incurred_at", "location", "comment", "recorded_by", "recorded_at"]
        read_only_fields = fields


class VehicleAssignSerializer(serializers.Serializer):
    location = serializers.ChoiceField(choices=VehicleLocation.choices)
    driver_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    override = serializers.BooleanField(required=False, default=False)
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")


class VehicleReleaseSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class VehicleMaintenanceSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["start", "end"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    next_service_due_date = serializers.DateField(required=False, allow_null=True)


class VehicleCostLogCreateSerializer(serializers.Serializer):
    cost_type = serializers.ChoiceField(choices=CostType.choices)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    incurred_at = serializers.DateField()
    location = serializers.ChoiceField(choices=VehicleLocation.choices, required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
