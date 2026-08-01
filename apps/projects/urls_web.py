from django.urls import path

from apps.projects import web_views

app_name = "projects_web"

urlpatterns = [
    path("projects/", web_views.ProjectListView.as_view(), name="list"),
    path("projects/create/", web_views.ProjectCreateView.as_view(), name="create"),
    path("projects/<int:pk>/", web_views.ProjectDetailView.as_view(), name="detail"),
    path("projects/<int:pk>/dispatch/", web_views.ProjectDispatchView.as_view(), name="dispatch"),
    path("projects/<int:pk>/return/", web_views.ProjectReturnView.as_view(), name="return"),
    path("projects/<int:pk>/equipment/assign/", web_views.ProjectEquipmentAssignView.as_view(), name="equipment-assign"),
    path(
        "projects/<int:pk>/equipment/<int:equipment_id>/release/",
        web_views.ProjectEquipmentReleaseView.as_view(), name="equipment-release",
    ),
    path("projects/<int:pk>/vehicles/assign/", web_views.ProjectVehicleAssignView.as_view(), name="vehicle-assign"),
    path(
        "projects/<int:pk>/vehicles/<int:vehicle_id>/release/",
        web_views.ProjectVehicleReleaseView.as_view(), name="vehicle-release",
    ),
    path("projects/<int:pk>/shift-logs/", web_views.ShiftLogCreateView.as_view(), name="shift-log-create"),
    path("projects/<int:pk>/toolbox-talks/create/", web_views.ToolboxTalkCreateView.as_view(), name="toolbox-talk-create"),
    path(
        "projects/<int:pk>/toolbox-talks/<int:talk_id>/",
        web_views.ToolboxTalkDetailView.as_view(), name="toolbox-talk-detail",
    ),
    path(
        "projects/<int:pk>/toolbox-talks/<int:talk_id>/attendees/<int:attendee_id>/sign/",
        web_views.ToolboxTalkSignView.as_view(), name="toolbox-talk-sign",
    ),
    path(
        "projects/<int:pk>/toolbox-talks/<int:talk_id>/attendees/<int:attendee_id>/resend-email/",
        web_views.ToolboxTalkResendEmailView.as_view(), name="toolbox-talk-resend-email",
    ),
    path("toolbox-talk/sign/<str:token>/", web_views.ToolboxTalkPublicSignView.as_view(), name="toolbox-talk-sign-public"),
    path("projects/<int:pk>/close/", web_views.ProjectCloseView.as_view(), name="close"),
]
