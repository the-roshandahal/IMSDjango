def handle_low_stock_signal(sender, product, warehouse_id, quantity, **kwargs):
    from apps.notifications.services import notify_low_stock
    from apps.warehouses.models import Warehouse

    warehouse = Warehouse.objects.get(pk=warehouse_id)
    notify_low_stock(product, warehouse, quantity)
