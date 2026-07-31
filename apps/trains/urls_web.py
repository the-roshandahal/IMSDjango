from django.urls import path

from apps.trains import web_views

app_name = "trains_web"

urlpatterns = [
    path("trains/", web_views.TrainLookupView.as_view(), name="lookup"),
]
