from django.apps import AppConfig


class EquipmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.equipment'
    label = 'equipment'

    def ready(self):
        from apps.accounts.services import register_reassignment_check
        from apps.equipment.services import check_assigned_equipment

        register_reassignment_check(check_assigned_equipment)
