from django.apps import AppConfig


class VehiclesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.vehicles'
    label = 'vehicles'

    def ready(self):
        from apps.accounts.services import register_reassignment_check
        from apps.vehicles.services import check_assigned_vehicles

        register_reassignment_check(check_assigned_vehicles)
