from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts import views
from apps.accounts.web_views import DashboardView, LoginPageView, LogoutPageView, TwoFactorPageView

app_name = "accounts"

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")

api_urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="api-login"),
    path("auth/logout", views.LogoutView.as_view(), name="api-logout"),
    path("auth/password/change", views.ChangePasswordView.as_view(), name="api-password-change"),
    path("auth/password/reset-request", views.PasswordResetRequestView.as_view(), name="api-password-reset-request"),
    path("auth/password/reset-confirm", views.PasswordResetConfirmView.as_view(), name="api-password-reset-confirm"),
    path("auth/2fa/enable", views.TwoFactorEnableView.as_view(), name="api-2fa-enable"),
    path("auth/2fa/verify", views.TwoFactorVerifyView.as_view(), name="api-2fa-verify"),
    path("users/<int:pk>/deactivate", views.UserDeactivateView.as_view(), name="api-user-deactivate"),
    path("users/<int:pk>/reactivate", views.UserReactivateView.as_view(), name="api-user-reactivate"),
    path("users/<int:pk>/unlock", views.UserUnlockView.as_view(), name="api-user-unlock"),
    path("users/<int:pk>/role", views.UserRoleChangeView.as_view(), name="api-user-role"),
    path("", include(router.urls)),
]

web_urlpatterns = [
    path("login/", LoginPageView.as_view(), name="login"),
    path("login/2fa/", TwoFactorPageView.as_view(), name="login-2fa"),
    path("logout/", LogoutPageView.as_view(), name="logout"),
    path("", DashboardView.as_view(), name="dashboard"),
]

urlpatterns = web_urlpatterns + [path("api/", include(api_urlpatterns))]
