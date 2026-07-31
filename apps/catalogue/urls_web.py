from django.urls import path

from apps.catalogue import web_views

app_name = "catalogue_web"

urlpatterns = [
    path("products/", web_views.ProductListView.as_view(), name="product-list"),
    path("products/create/", web_views.ProductCreateView.as_view(), name="product-create"),
    path("products/<int:pk>/", web_views.ProductDetailView.as_view(), name="product-detail"),
    path("products/<int:pk>/edit/", web_views.ProductUpdateView.as_view(), name="product-edit"),
    path("products/<int:pk>/archive/", web_views.ProductArchiveView.as_view(), name="product-archive"),
    path("products/<int:pk>/delete/", web_views.ProductDeleteView.as_view(), name="product-delete"),
    path("categories/", web_views.CategoryListView.as_view(), name="category-list"),
    path("categories/create/", web_views.CategoryCreateView.as_view(), name="category-create"),
]
