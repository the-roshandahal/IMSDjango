from django.urls import path

from apps.employees import web_views

app_name = "employees_web"

urlpatterns = [
    path("employees/", web_views.EmployeeListView.as_view(), name="list"),
    path("employees/create/", web_views.EmployeeCreateView.as_view(), name="create"),
    path("employees/<int:pk>/", web_views.EmployeeDetailView.as_view(), name="detail"),
    path("employees/<int:pk>/edit/", web_views.EmployeeUpdateView.as_view(), name="edit"),
    path("employees/<int:pk>/resend-invite/", web_views.EmployeeResendInviteView.as_view(), name="resend-invite"),
    path("employees/<int:pk>/deactivate/", web_views.EmployeeDeactivateView.as_view(), name="deactivate"),
    path("employees/<int:pk>/reactivate/", web_views.EmployeeReactivateView.as_view(), name="reactivate"),
    path("employees/<int:pk>/create-login/", web_views.EmployeeCreateLoginView.as_view(), name="create-login"),
    path("employees/<int:pk>/set-kiosk-pin/", web_views.EmployeeSetKioskPinView.as_view(), name="set-kiosk-pin"),
    path("employees/<int:pk>/site-assignments/add/", web_views.EmployeeSiteAssignmentCreateView.as_view(), name="site-assignment-create"),
    path("employees/<int:pk>/site-assignments/<int:assignment_id>/delete/", web_views.EmployeeSiteAssignmentDeleteView.as_view(), name="site-assignment-delete"),
    path("onboard/<str:token>/", web_views.EmployeeOnboardingView.as_view(), name="onboard"),
]
