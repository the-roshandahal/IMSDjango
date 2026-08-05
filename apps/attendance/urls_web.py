from django.urls import path

from apps.attendance import web_views

app_name = "attendance_web"

urlpatterns = [
    path("attendance/", web_views.AttendanceOverviewView.as_view(), name="overview"),
    path("attendance/stations/<int:pk>/", web_views.StationAttendanceHubView.as_view(), name="station-hub"),
    path("attendance/stations/<int:pk>/duty-sheets/create/", web_views.DutySheetCreateView.as_view(), name="duty-sheet-create"),
    path("attendance/duty-sheets/<int:pk>/assign/", web_views.DutySheetAssignView.as_view(), name="duty-sheet-assign"),
    path("attendance/duty-sheets/<int:pk>/", web_views.DutySheetDetailView.as_view(), name="duty-sheet-detail"),
    path("attendance/duty-sheets/<int:pk>/toggle/", web_views.DutySheetToggleActiveView.as_view(), name="duty-sheet-toggle"),
    path("attendance/duty-sheets/<int:pk>/tasks/add/", web_views.DutySheetAddTaskView.as_view(), name="task-add"),
    path("attendance/tasks/<int:pk>/toggle-active/", web_views.DutySheetTaskToggleActiveView.as_view(), name="task-toggle-active"),

    path("attendance/clock/", web_views.SelfClockView.as_view(), name="clock"),
    path("attendance/clock-out/<int:pk>/", web_views.ClockOutView.as_view(), name="clock-out"),
    path("attendance/tasks/<int:pk>/complete/", web_views.DutySheetTaskCompleteView.as_view(), name="task-complete"),
    path("attendance/tasks/<int:pk>/undo/", web_views.DutySheetTaskUndoView.as_view(), name="task-undo"),
    path("kiosk/<str:token>/", web_views.KioskEntryView.as_view(), name="kiosk"),
]
