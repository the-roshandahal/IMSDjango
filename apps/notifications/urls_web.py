from django.urls import path

from apps.notifications import web_views

app_name = "notifications_web"

urlpatterns = [
    path("notifications/", web_views.NotificationListView.as_view(), name="list"),
    path("notifications/<int:pk>/read/", web_views.NotificationReadView.as_view(), name="read"),
    path("notifications/mark-all-read/", web_views.NotificationMarkAllReadView.as_view(), name="mark-all-read"),
]
