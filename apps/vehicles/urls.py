from rest_framework.routers import DefaultRouter

from apps.vehicles.views import VehicleViewSet

app_name = "vehicles"

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")

urlpatterns = router.urls
