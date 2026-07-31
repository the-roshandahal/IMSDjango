from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalogue import services
from apps.catalogue.models import Category, Product
from apps.catalogue.serializers import BatchSerializer, CategorySerializer, ProductSerializer
from apps.core.permissions import CapabilityPermission


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability_map = {"GET": "product.view", "POST": "product.manage", "PUT": "product.manage", "PATCH": "product.manage"}
    http_method_names = ["get", "post", "put", "head", "options"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, CapabilityPermission]
    capability_map = {"GET": "product.view", "POST": "product.manage", "PUT": "product.manage", "PATCH": "product.manage"}
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("include_archived") != "true":
            qs = qs.filter(is_archived=False)
        return qs

    def perform_create(self, serializer):
        product = serializer.save()
        services.provision_codes(product)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.is_archived = True
        product.save(update_fields=["is_archived"])
        return Response(ProductSerializer(product).data)

    @action(detail=True, methods=["get", "post"], url_path="batches")
    def batches(self, request, pk=None):
        product = self.get_object()
        if request.method == "POST":
            serializer = BatchSerializer(data={**request.data, "product": product.pk})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        qs = product.batches.select_related("warehouse")
        return Response(BatchSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="barcode/(?P<code>[^/]+)")
    def by_barcode(self, request, code=None):
        product = get_object_or_404(Product, barcode=code, is_archived=False)
        return Response(ProductSerializer(product).data)
