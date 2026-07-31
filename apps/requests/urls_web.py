from django.urls import path

from apps.requests import web_views

app_name = "stock_requests_web"

urlpatterns = [
    path("stock-requests/", web_views.StockRequestListView.as_view(), name="list"),
    path("stock-requests/<int:pk>/", web_views.StockRequestDetailView.as_view(), name="detail"),
    path("stock-requests/<int:pk>/approve/", web_views.StockRequestApproveView.as_view(), name="approve"),
    path("stock-requests/<int:pk>/reject/", web_views.StockRequestRejectView.as_view(), name="reject"),
    path("stock-requests/<int:pk>/dispatch/", web_views.StockRequestDispatchView.as_view(), name="dispatch"),
    path("stations/<int:station_id>/requests/new/", web_views.StockRequestCreateView.as_view(), name="create"),
]
