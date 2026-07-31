from django.urls import path

from apps.inventory import web_views

app_name = "inventory_web"

urlpatterns = [
    path("inventory/transactions/", web_views.TransactionListView.as_view(), name="transaction-list"),
    path("inventory/new/", web_views.NewTransactionView.as_view(), name="new-transaction"),
    path("inventory/station-usage/", web_views.StationUsageWebView.as_view(), name="station-usage"),
]
