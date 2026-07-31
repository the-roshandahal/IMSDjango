from rest_framework.routers import DefaultRouter

from apps.equipment.views import EquipmentViewSet

app_name = "equipment"

router = DefaultRouter()
router.register("equipment", EquipmentViewSet, basename="equipment")

urlpatterns = router.urls
