from django.urls import path

from apps.suppliers import web_views

app_name = "suppliers_web"

urlpatterns = [
    path("suppliers/", web_views.SupplierListView.as_view(), name="list"),
    path("suppliers/create/", web_views.SupplierCreateView.as_view(), name="create"),
    path("suppliers/<int:pk>/", web_views.SupplierDetailView.as_view(), name="detail"),
    path("suppliers/<int:pk>/edit/", web_views.SupplierUpdateView.as_view(), name="edit"),
    path("suppliers/<int:pk>/products/add/", web_views.SupplierProductAddView.as_view(), name="product-add"),
    path(
        "suppliers/<int:pk>/products/<int:sp_id>/remove/",
        web_views.SupplierProductRemoveView.as_view(), name="product-remove",
    ),
]
