from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    path("inventory/stock-in", views.StockInView.as_view(), name="stock-in"),
    path("inventory/stock-out", views.StockOutView.as_view(), name="stock-out"),
    path("inventory/transfer", views.TransferInitiateView.as_view(), name="transfer-initiate"),
    path("inventory/transfer/<int:pk>/confirm", views.TransferConfirmView.as_view(), name="transfer-confirm"),
    path("inventory/adjustment", views.AdjustmentView.as_view(), name="adjustment"),
    path("inventory/return", views.ReturnView.as_view(), name="return"),
    path("inventory/station-usage", views.StationUsageView.as_view(), name="station-usage"),
    path("inventory/damaged", views.DamagedView.as_view(), name="damaged"),
    path("inventory/lost", views.LostView.as_view(), name="lost"),
    path("inventory/expired", views.ExpiredView.as_view(), name="expired"),
    path("inventory/transactions", views.TransactionListView.as_view(), name="transactions"),
    path("inventory/stocktake", views.StocktakeCreateView.as_view(), name="stocktake-create"),
    path("inventory/stocktake/<int:pk>/variance", views.StocktakeVarianceView.as_view(), name="stocktake-variance"),
]
