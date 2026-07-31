import django.dispatch

# Fired after any stock-decreasing transaction leaves a product at/below its
# reorder point. No listener exists yet -- the future Notifications module
# (Section 5.13) connects a receiver here with zero change to inventory code.
low_stock_signal = django.dispatch.Signal()  # kwargs: product, warehouse_id, quantity
