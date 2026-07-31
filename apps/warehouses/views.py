from django.db.models import Sum
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    SITE_SCOPE_EXEMPT_ROLES,
    CapabilityPermission,
    assigned_site_ids,
    ensure_site_access,
)
from apps.warehouses.models import Station, Warehouse
from apps.warehouses.serializers import StationSerializer, StockSummarySerializer, WarehouseSerializer


class WarehouseViewSet(viewsets.ModelViewSet):
    """Warehouse *is* the site here (not a field pointing at one), so
    scoping is done by filtering the queryset to the user's SiteAssignments
    rather than via SiteScopedPermission's object.<site_field> lookup —
    out-of-scope warehouses simply 404 on retrieve/update, same as any
    other filtered-queryset DRF viewset."""

    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability_map = {"GET": "product.view", "POST": "warehouse.manage", "PUT": "warehouse.manage"}
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in SITE_SCOPE_EXEMPT_ROLES:
            return qs
        return qs.filter(pk__in=list(assigned_site_ids(user, "warehouse")))

    @action(detail=True, methods=["get"], url_path="stock")
    def stock(self, request, pk=None):
        from apps.inventory.models import StockLevel  # local import: avoids a hard app-load-order dependency

        warehouse = self.get_object()
        qs = (
            StockLevel.objects.filter(warehouse=warehouse, quantity__gt=0)
            .values("product__id", "product__name", "batch__id")
            .annotate(quantity=Sum("quantity"))
            .order_by("product__name")
        )
        return Response(StockSummarySerializer(qs, many=True).data)


class StationViewSet(viewsets.ModelViewSet):
    queryset = Station.objects.filter(is_active=True)
    serializer_class = StationSerializer
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability_map = {"GET": "product.view", "POST": "warehouse.manage", "PUT": "warehouse.manage"}
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in SITE_SCOPE_EXEMPT_ROLES:
            return qs
        return qs.filter(pk__in=list(assigned_site_ids(user, "station")))

    @action(detail=True, methods=["get"], url_path="stock")
    def stock(self, request, pk=None):
        from apps.inventory.models import StockLevel

        station = self.get_object()
        qs = (
            StockLevel.objects.filter(station=station, quantity__gt=0)
            .values("product__id", "product__name", "batch__id")
            .annotate(quantity=Sum("quantity"))
            .order_by("product__name")
        )
        return Response(StockSummarySerializer(qs, many=True).data)
