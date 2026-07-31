from django.urls import path

from apps.documents import web_views

app_name = "documents_web"

urlpatterns = [
    path("documents/upload/<str:model_key>/<int:object_id>/", web_views.DocumentUploadView.as_view(), name="upload"),
    path("documents/<int:pk>/delete/", web_views.DocumentDeleteView.as_view(), name="delete"),
]
