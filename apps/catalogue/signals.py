import django.dispatch

# Fired after any stock-decreasing transaction leaves a product at/below its
# reorder point, at a warehouse or a station (mutually exclusive -- exactly
# one of warehouse_id/station_id is set). apps.notifications connects a
# receiver here with zero change to inventory code.
low_stock_signal = django.dispatch.Signal()  # kwargs: product, warehouse_id, station_id, vehicle_id, quantity, reorder_point
