from django.urls import path

from apps.requests import views

app_name = "stock_requests"

urlpatterns = [
    path("stations/<int:station_id>/requests", views.StationStockRequestCreateView.as_view(), name="station-request-create"),
    path("stock-requests", views.StockRequestListView.as_view(), name="stock-request-list"),
    path("stock-requests/<int:pk>/approve", views.StockRequestApproveView.as_view(), name="stock-request-approve"),
    path("stock-requests/<int:pk>/reject", views.StockRequestRejectView.as_view(), name="stock-request-reject"),
    path("stock-requests/<int:pk>/dispatch", views.StockRequestDispatchView.as_view(), name="stock-request-dispatch"),
]
