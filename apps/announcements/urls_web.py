from django.urls import path

from apps.announcements import web_views

app_name = "announcements_web"

urlpatterns = [
    path("announcements/", web_views.AnnouncementListView.as_view(), name="list"),
    path("announcements/create/", web_views.AnnouncementCreateView.as_view(), name="create"),
    path("announcements/<int:pk>/", web_views.AnnouncementDetailView.as_view(), name="detail"),
    path("announcements/<int:pk>/read/", web_views.AnnouncementMarkReadView.as_view(), name="mark-read"),
]
