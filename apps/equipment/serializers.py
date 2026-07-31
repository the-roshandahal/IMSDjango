from rest_framework import serializers

from apps.equipment.models import Equipment, EquipmentLog, TestResult


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = [
            "id", "asset_id", "name", "serial_number", "qr_code_data", "qr_code_image",
            "status", "current_warehouse", "current_station", "assigned_user",
            "maintenance_interval_days", "last_maintenance_at", "next_maintenance_due",
            "test_interval_days", "last_test_date", "next_test_due", "last_test_result", "last_tested_by",
            "created_at",
        ]
        read_only_fields = [
            "id", "qr_code_data", "qr_code_image", "status", "current_warehouse", "current_station",
            "assigned_user", "last_maintenance_at", "next_maintenance_due", "last_test_date", "next_test_due",
            "last_test_result", "last_tested_by", "created_at",
        ]


class EquipmentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentLog
        fields = ["id", "action", "station", "assigned_user", "override_used", "comment", "performed_by", "timestamp"]
        read_only_fields = fields


class EquipmentAssignSerializer(serializers.Serializer):
    station_id = serializers.IntegerField()
    assigned_user_id = serializers.IntegerField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    override = serializers.BooleanField(required=False, default=False)
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")


class EquipmentReleaseSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)


class EquipmentMaintenanceSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["start", "end"])
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)


class EquipmentTestSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=TestResult.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
