from rest_framework.routers import DefaultRouter

from apps.warehouses.views import StationViewSet, WarehouseViewSet

app_name = "warehouses"

router = DefaultRouter()
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("stations", StationViewSet, basename="station")

urlpatterns = router.urls
