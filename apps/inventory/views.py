from decimal import Decimal

from django.db import models as django_models
from django.db.utils import OperationalError
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import CapabilityPermission, ensure_site_access
from apps.inventory import services
from apps.inventory.exceptions import ApprovalRequiredError, InsufficientStockError, StockLevelChangedError
from apps.inventory.models import InventoryTransaction, Stocktake, StocktakeLine, StockLevel, Transfer
from apps.inventory.serializers import (
    AdjustmentSerializer,
    DamagedSerializer,
    ExpiredSerializer,
    InventoryTransactionSerializer,
    LostSerializer,
    ReturnSerializer,
    StationUsageSerializer,
    StockInSerializer,
    StockOutSerializer,
    StocktakeCreateSerializer,
    StocktakeSerializer,
    TransferInitiateSerializer,
    TransferSerializer,
)


def _database_busy_response(exc: OperationalError) -> Response:
    """Raises the original exception back out if it isn't lock contention
    (a genuine bug shouldn't be swallowed as a 409)."""
    if "locked" not in str(exc).lower():
        raise exc
    return Response(
        {"error": "database_busy", "message": "Database is busy, please retry.", "retryable": True},
        status=status.HTTP_409_CONFLICT,
    )


class StockActionView(APIView):
    """Shared plumbing for the thin stock-mutation endpoints: validate,
    check site scope, call the matching services.py function, translate
    domain exceptions to HTTP status."""

    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "warehouse.stock.manage"
    serializer_class = None

    def get_scope_ids(self, data):
        return {"warehouse_id": data.get("warehouse_id"), "station_id": data.get("station_id")}

    def call_service(self, data, user):
        raise NotImplementedError

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ensure_site_access(request.user, **self.get_scope_ids(data))
        try:
            result = self.call_service(data, request.user)
        except StockLevelChangedError as exc:
            return Response({"error": "stock_level_changed", "message": str(exc), "retryable": True}, status=status.HTTP_409_CONFLICT)
        except InsufficientStockError as exc:
            return Response({"error": "insufficient_stock", "message": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ApprovalRequiredError as exc:
            return Response({"error": "approval_required", "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except OperationalError as exc:
            # SQLite's own file-level write-lock contention ("database is
            # locked") under heavy concurrent writers -- a distinct error
            # class from StockLevelChangedError but equally safe to retry;
            # never a sign of a corrupted balance. Disappears under Postgres.
            return _database_busy_response(exc)
        return self.respond(result)

    def respond(self, result):
        if isinstance(result, list):
            return Response(InventoryTransactionSerializer(result, many=True).data, status=status.HTTP_201_CREATED)
        return Response(InventoryTransactionSerializer(result).data, status=status.HTTP_201_CREATED)


class StockInView(StockActionView):
    serializer_class = StockInSerializer

    def call_service(self, data, user):
        return services.stock_in(performed_by=user, **data)


class StockOutView(StockActionView):
    serializer_class = StockOutSerializer

    def call_service(self, data, user):
        return services.stock_out(performed_by=user, **data)


class StationUsageView(StockActionView):
    """Record daily consumption of stock already held at a station (SRS
    Section 5.6). Distinct capability from warehouse-side stock actions --
    station staff record their own usage but don't manage warehouse stock."""

    serializer_class = StationUsageSerializer
    capability = "station.usage.record"

    def call_service(self, data, user):
        return services.station_stock_usage(performed_by=user, **data)


class AdjustmentView(StockActionView):
    serializer_class = AdjustmentSerializer

    def call_service(self, data, user):
        return services.adjustment(performed_by=user, **data)


class ReturnView(StockActionView):
    serializer_class = ReturnSerializer

    def call_service(self, data, user):
        return services.return_stock(performed_by=user, **data)


class DamagedView(StockActionView):
    serializer_class = DamagedSerializer

    def call_service(self, data, user):
        return services.record_damaged(performed_by=user, **data)


class LostView(StockActionView):
    """Recording lost stock requires Supervisor sign-off (SRS Section 5.4).
    The requesting supervisor/admin's own action serves as that sign-off."""

    serializer_class = LostSerializer

    def call_service(self, data, user):
        return services.record_lost(performed_by=user, approved_by=user, **data)


class ExpiredView(StockActionView):
    serializer_class = ExpiredSerializer

    def call_service(self, data, user):
        return services.record_expired(performed_by=user, **data)


class TransferInitiateView(APIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "warehouse.stock.manage"

    def post(self, request):
        serializer = TransferInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ensure_site_access(request.user, warehouse_id=data["source_warehouse_id"], station_id=data.get("dest_station_id"))
        try:
            transfer = services.transfer_initiate(initiated_by=request.user, **data)
        except StockLevelChangedError as exc:
            return Response({"error": "stock_level_changed", "message": str(exc), "retryable": True}, status=status.HTTP_409_CONFLICT)
        except InsufficientStockError as exc:
            return Response({"error": "insufficient_stock", "message": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except OperationalError as exc:
            return _database_busy_response(exc)
        return Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)


class TransferConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "warehouse.stock.manage"

    def post(self, request, pk):
        transfer = Transfer.objects.filter(pk=pk).first()
        if transfer is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ensure_site_access(request.user, warehouse_id=transfer.dest_warehouse_id, station_id=transfer.dest_station_id)
        try:
            transfer = services.transfer_confirm_receipt(transfer_id=pk, confirmed_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except OperationalError as exc:
            return _database_busy_response(exc)
        return Response(TransferSerializer(transfer).data)


class TransactionFilterSet(filters.FilterSet):
    date_from = filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    date_to = filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = InventoryTransaction
        fields = {
            "product": ["exact"],
            "type": ["exact"],
            "source_warehouse": ["exact"],
            "dest_warehouse": ["exact"],
            "station": ["exact"],
        }


class TransactionListView(generics.ListAPIView):
    """GET /inventory/transactions -- filterable by product, location, date range."""

    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "warehouse.stock.manage"  # read access; broadened per-role in get_queryset below
    serializer_class = InventoryTransactionSerializer
    filterset_class = TransactionFilterSet
    queryset = InventoryTransaction.objects.select_related(
        "product", "batch", "source_warehouse", "dest_warehouse", "station", "performed_by"
    )

    def get_queryset(self):
        from apps.core.permissions import assigned_site_ids, SITE_SCOPE_EXEMPT_ROLES

        qs = super().get_queryset()
        user = self.request.user
        if user.role in SITE_SCOPE_EXEMPT_ROLES:
            return qs
        warehouse_ids = list(assigned_site_ids(user, "warehouse"))
        station_ids = list(assigned_site_ids(user, "station"))
        return qs.filter(
            django_models.Q(source_warehouse_id__in=warehouse_ids)
            | django_models.Q(dest_warehouse_id__in=warehouse_ids)
            | django_models.Q(station_id__in=station_ids)
        )


class StocktakeCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "stocktake.manage"

    def post(self, request):
        serializer = StocktakeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ensure_site_access(request.user, warehouse_id=data["warehouse_id"])

        stocktake = Stocktake.objects.create(warehouse_id=data["warehouse_id"], started_by=request.user)
        lines = []
        for line in data["lines"]:
            system_qty = (
                StockLevel.objects.filter(
                    product_id=line["product_id"], warehouse_id=data["warehouse_id"],
                    station=None, batch_id=line.get("batch_id"),
                ).values_list("quantity", flat=True).first()
                or Decimal("0")
            )
            lines.append(
                StocktakeLine(
                    stocktake=stocktake, product_id=line["product_id"], batch_id=line.get("batch_id"),
                    system_quantity=system_qty, counted_quantity=line["counted_quantity"],
                )
            )
        StocktakeLine.objects.bulk_create(lines)
        stocktake.status = "completed"
        stocktake.completed_at = timezone.now()
        stocktake.save(update_fields=["status", "completed_at"])
        return Response(StocktakeSerializer(stocktake).data, status=status.HTTP_201_CREATED)


class StocktakeVarianceView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability = "stocktake.manage"
    serializer_class = StocktakeSerializer
    queryset = Stocktake.objects.prefetch_related("lines")
