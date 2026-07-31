from django.db.models import Q
from django.db.utils import OperationalError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import (
    SITE_SCOPE_EXEMPT_ROLES,
    CapabilityPermission,
    assigned_site_ids,
    ensure_site_access,
)
from apps.requests import services
from apps.requests.models import StockRequest
from apps.requests.serializers import (
    StockRequestCreateSerializer,
    StockRequestRejectSerializer,
    StockRequestSerializer,
)
from apps.requests.services import RequestNotApprovedError


def _database_busy_response(exc: OperationalError) -> Response:
    if "locked" not in str(exc).lower():
        raise exc
    return Response(
        {"error": "database_busy", "message": "Database is busy, please retry.", "retryable": True},
        status=status.HTTP_409_CONFLICT,
    )


class StationStockRequestCreateView(APIView):
    """POST /stations/{station_id}/requests (SRS Section 8.5)."""

    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "station_request.create"

    def post(self, request, station_id):
        serializer = StockRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ensure_site_access(request.user, station_id=station_id)
        req = services.create_request(
            station_id=station_id, warehouse_id=data["warehouse_id"], requested_by=request.user,
            lines=[{"product_id": line["product_id"], "quantity": line["quantity"]} for line in data["lines"]],
        )
        return Response(StockRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class StockRequestListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "station_request.view"
    serializer_class = StockRequestSerializer
    queryset = StockRequest.objects.select_related("station", "warehouse", "requested_by", "approved_by").prefetch_related(
        "lines"
    )

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in SITE_SCOPE_EXEMPT_ROLES:
            return qs
        warehouse_ids = list(assigned_site_ids(user, "warehouse"))
        station_ids = list(assigned_site_ids(user, "station"))
        return qs.filter(
            Q(warehouse_id__in=warehouse_ids) | Q(station_id__in=station_ids) | Q(requested_by=user)
        )


class StockRequestApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "station_request.approve"

    def post(self, request, pk):
        stock_request = StockRequest.objects.filter(pk=pk).first()
        if stock_request is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ensure_site_access(request.user, warehouse_id=stock_request.warehouse_id)
        try:
            req = services.approve_request(request_id=pk, approved_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(StockRequestSerializer(req).data)


class StockRequestRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "station_request.approve"

    def post(self, request, pk):
        stock_request = StockRequest.objects.filter(pk=pk).first()
        if stock_request is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ensure_site_access(request.user, warehouse_id=stock_request.warehouse_id)
        serializer = StockRequestRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            req = services.reject_request(
                request_id=pk, approved_by=request.user, reason=serializer.validated_data["reason"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(StockRequestSerializer(req).data)


class StockRequestDispatchView(APIView):
    """Dispatches an approved request -- thin wrapper around
    apps.inventory.services.stock_out per line (SRS Section 5.4: 'Stock
    cannot be dispatched against a request that has not been approved')."""

    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "warehouse.stock.manage"

    def post(self, request, pk):
        stock_request = StockRequest.objects.filter(pk=pk).first()
        if stock_request is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ensure_site_access(request.user, warehouse_id=stock_request.warehouse_id)
        try:
            req, shortfall = services.dispatch_request(request_id=pk, dispatched_by=request.user)
        except RequestNotApprovedError as exc:
            return Response({"error": "not_approved", "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except OperationalError as exc:
            return _database_busy_response(exc)
        payload = StockRequestSerializer(req).data
        payload["shortfall"] = shortfall
        return Response(payload)
