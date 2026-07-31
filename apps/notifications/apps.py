from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"

    def ready(self):
        from apps.catalogue.signals import low_stock_signal
        from apps.notifications.receivers import handle_low_stock_signal

        low_stock_signal.connect(handle_low_stock_signal)
