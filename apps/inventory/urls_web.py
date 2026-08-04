from django.urls import path

from apps.inventory import web_views

app_name = "inventory_web"

urlpatterns = [
    path("inventory/transactions/", web_views.TransactionListView.as_view(), name="transaction-list"),
    path("inventory/new/", web_views.NewTransactionView.as_view(), name="new-transaction"),
    path("inventory/station-usage/", web_views.StationUsageWebView.as_view(), name="station-usage"),
    path("inventory/stocktakes/", web_views.StocktakeListView.as_view(), name="stocktake-list"),
    path("inventory/stocktakes/new/", web_views.StocktakeCreateView.as_view(), name="stocktake-new"),
    path("inventory/stocktakes/<int:pk>/", web_views.StocktakeDetailView.as_view(), name="stocktake-detail"),
    path(
        "inventory/thresholds/<str:site_type>/<int:site_id>/<int:product_id>/edit/",
        web_views.ThresholdEditView.as_view(), name="threshold-edit",
    ),
]
