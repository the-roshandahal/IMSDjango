from rest_framework import permissions, viewsets
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import CapabilityPermission
from apps.vehicles import services
from apps.vehicles.models import Vehicle
from apps.vehicles.serializers import (
    VehicleAssignSerializer,
    VehicleCostLogCreateSerializer,
    VehicleCostLogSerializer,
    VehicleMaintenanceSerializer,
    VehicleReleaseSerializer,
    VehicleSerializer,
)
from apps.vehicles.services import ComplianceBlockedError, VehicleUnavailableError


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("assigned_driver")
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability_map = {"GET": "vehicle.view_own", "POST": "vehicle.manage", "PUT": "vehicle.manage"}
    http_method_names = ["get", "post", "put", "head", "options"]

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        serializer = VehicleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            vehicle = services.assign_to_location(
                vehicle_id=pk, location=data["location"], driver_id=data.get("driver_id"),
                performed_by=request.user, comment=data["comment"], override=data["override"],
                override_reason=data["override_reason"],
            )
        except ComplianceBlockedError as exc:
            return Response({"error": "compliance_blocked", "blockers": exc.blockers}, status=http_status.HTTP_400_BAD_REQUEST)
        except VehicleUnavailableError as exc:
            return Response({"error": "unavailable", "message": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        serializer = VehicleReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vehicle = services.release(vehicle_id=pk, performed_by=request.user, comment=serializer.validated_data["comment"])
        except VehicleUnavailableError as exc:
            return Response({"error": "unavailable", "message": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=True, methods=["post"])
    def maintenance(self, request, pk=None):
        serializer = VehicleMaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            if data["action"] == "start":
                vehicle = services.start_maintenance(vehicle_id=pk, performed_by=request.user, comment=data["comment"])
            else:
                vehicle = services.end_maintenance(
                    vehicle_id=pk, performed_by=request.user, comment=data["comment"],
                    next_service_due_date=data.get("next_service_due_date"),
                )
        except VehicleUnavailableError as exc:
            return Response({"error": "unavailable", "message": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=True, methods=["post"], url_path="cost-log")
    def cost_log(self, request, pk=None):
        serializer = VehicleCostLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        entry = services.log_cost(
            vehicle_id=pk, cost_type=data["cost_type"], amount=data["amount"], incurred_at=data["incurred_at"],
            recorded_by=request.user, comment=data["comment"], location=data.get("location"),
        )
        return Response(VehicleCostLogSerializer(entry).data, status=http_status.HTTP_201_CREATED)
