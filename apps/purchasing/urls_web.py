from django.urls import path

from apps.purchasing import web_views

app_name = "purchasing_web"

urlpatterns = [
    path("purchase-orders/", web_views.PurchaseOrderListView.as_view(), name="list"),
    path("purchase-orders/create/", web_views.PurchaseOrderCreateView.as_view(), name="create"),
    path("purchase-orders/<int:pk>/", web_views.PurchaseOrderDetailView.as_view(), name="detail"),
    path("purchase-orders/<int:pk>/print/", web_views.PurchaseOrderPrintView.as_view(), name="print"),
    path("purchase-orders/<int:pk>/send/", web_views.PurchaseOrderSendView.as_view(), name="send"),
    path("purchase-orders/<int:pk>/cancel/", web_views.PurchaseOrderCancelView.as_view(), name="cancel"),
    path("purchase-orders/<int:pk>/lines/add/", web_views.PurchaseOrderLineAddView.as_view(), name="line-add"),
    path(
        "purchase-orders/<int:pk>/lines/<int:line_id>/remove/",
        web_views.PurchaseOrderLineRemoveView.as_view(), name="line-remove",
    ),
    path(
        "purchase-orders/<int:pk>/lines/<int:line_id>/receive/",
        web_views.PurchaseOrderReceiveLineView.as_view(), name="line-receive",
    ),
]
