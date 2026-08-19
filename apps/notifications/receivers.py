def handle_low_stock_signal(
    sender, product, quantity, reorder_point, warehouse_id=None, station_id=None, vehicle_id=None, **kwargs
):
    from apps.notifications.services import notify_low_stock

    if warehouse_id:
        from apps.warehouses.models import Warehouse

        notify_low_stock(product, quantity, reorder_point, warehouse=Warehouse.objects.get(pk=warehouse_id))
    elif station_id:
        from apps.warehouses.models import Station

        notify_low_stock(product, quantity, reorder_point, station=Station.objects.get(pk=station_id))
    elif vehicle_id:
        from apps.vehicles.models import Vehicle

        notify_low_stock(product, quantity, reorder_point, vehicle=Vehicle.objects.get(pk=vehicle_id))
