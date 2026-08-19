from django.urls import path

from apps.core import web_views

app_name = "core_web"

urlpatterns = [
    path("guide/", web_views.UserGuideView.as_view(), name="guide"),
    path("case-studies/<slug:slug>/", web_views.CaseStudyDetailView.as_view(), name="case-study"),
    path("offline/", web_views.OfflineView.as_view(), name="offline"),
]
