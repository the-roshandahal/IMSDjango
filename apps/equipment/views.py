from rest_framework import permissions, viewsets
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import CapabilityPermission, ensure_site_access
from apps.equipment import services
from apps.equipment.models import Equipment
from apps.equipment.serializers import (
    EquipmentAssignSerializer,
    EquipmentLogSerializer,
    EquipmentMaintenanceSerializer,
    EquipmentReleaseSerializer,
    EquipmentSerializer,
    EquipmentTestSerializer,
)
from apps.equipment.services import ComplianceBlockedError, EquipmentUnavailableError


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.select_related("current_warehouse", "current_station", "assigned_user")
    serializer_class = EquipmentSerializer
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability_map = {"GET": "equipment.view_own", "POST": "equipment.manage", "PUT": "equipment.manage"}
    http_method_names = ["get", "post", "put", "head", "options"]

    def perform_create(self, serializer):
        equipment = serializer.save()
        services.provision_qr_code(equipment)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        serializer = EquipmentAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ensure_site_access(request.user, station_id=data["station_id"])
        try:
            equipment = services.assign_to_station(
                equipment_id=pk, station_id=data["station_id"], assigned_user_id=data.get("assigned_user_id"),
                performed_by=request.user, comment=data["comment"], override=data["override"],
                override_reason=data["override_reason"],
            )
        except ComplianceBlockedError as exc:
            return Response({"error": "compliance_blocked", "blockers": exc.blockers}, status=http_status.HTTP_400_BAD_REQUEST)
        except EquipmentUnavailableError as exc:
            return Response({"error": "unavailable", "message": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        return Response(EquipmentSerializer(equipment).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        serializer = EquipmentReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            equipment = services.release(
                equipment_id=pk, performed_by=request.user, comment=data["comment"], warehouse_id=data.get("warehouse_id")
            )
        except EquipmentUnavailableError as exc:
            return Response({"error": "unavailable", "message": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        return Response(EquipmentSerializer(equipment).data)

    @action(detail=True, methods=["post"])
    def maintenance(self, request, pk=None):
        serializer = EquipmentMaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            if data["action"] == "start":
                equipment = services.start_maintenance(equipment_id=pk, performed_by=request.user, comment=data["comment"])
            else:
                equipment = services.end_maintenance(
                    equipment_id=pk, performed_by=request.user, comment=data["comment"],
                    warehouse_id=data.get("warehouse_id"),
                )
        except EquipmentUnavailableError as exc:
            return Response({"error": "unavailable", "message": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        return Response(EquipmentSerializer(equipment).data)

    @action(detail=True, methods=["post"], url_path="test")
    def record_test(self, request, pk=None):
        serializer = EquipmentTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        equipment = services.record_test(
            equipment_id=pk, result=data["result"], performed_by=request.user, comment=data["comment"]
        )
        return Response(EquipmentSerializer(equipment).data)

    @action(detail=True, methods=["get"], url_path="service-history")
    def service_history(self, request, pk=None):
        equipment = self.get_object()
        logs = equipment.logs.select_related("station", "assigned_user", "performed_by")
        return Response(EquipmentLogSerializer(logs, many=True).data)
