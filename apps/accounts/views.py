from django.contrib.auth import login, logout
from django.core.mail import send_mail
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import services, totp
from apps.accounts.models import PasswordResetToken, Role, User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TwoFactorVerifySerializer,
    UserCreateSerializer,
    UserDeactivateSerializer,
    UserRoleChangeSerializer,
    UserSerializer,
)
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        password = serializer.validated_data["password"]

        user, result = services.check_credentials(identifier, password, request=request)
        ip = get_client_ip(request)

        if result == services.LoginResult.OK:
            login(request, user)
            AuditLog.log(actor=user, action="auth.login_success", entity_type="User", entity_id=user.pk, ip_address=ip)
            return Response(UserSerializer(user).data)

        if result == services.LoginResult.REQUIRES_2FA:
            request.session["pending_2fa_user_id"] = user.pk
            AuditLog.log(
                actor=user, action="auth.login_password_ok_2fa_pending", entity_type="User",
                entity_id=user.pk, ip_address=ip,
            )
            return Response({"requires_2fa": True}, status=status.HTTP_200_OK)

        AuditLog.log(
            actor=user if user else None,
            action=f"auth.login_failed.{result}",
            entity_type="User",
            entity_id=user.pk if user else "",
            ip_address=ip,
            metadata={"identifier": identifier},
        )
        messages = {
            services.LoginResult.INVALID_CREDENTIALS: "Invalid credentials.",
            services.LoginResult.LOCKED: "Account is locked. Try again later or contact an administrator.",
            services.LoginResult.INACTIVE: "Account is deactivated.",
        }
        return Response({"detail": messages.get(result, "Login failed.")}, status=status.HTTP_401_UNAUTHORIZED)


class TwoFactorVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        ip = get_client_ip(request)

        if request.user.is_authenticated:
            # Confirming a fresh 2FA enrollment.
            device = TOTPDevice.objects.filter(user=request.user, name="default", confirmed=False).first()
            if device is None or not device.verify_token(token):
                return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            request.user.is_2fa_enabled = True
            request.user.save(update_fields=["is_2fa_enabled"])
            AuditLog.log(actor=request.user, action="auth.2fa_enabled", entity_type="User", entity_id=request.user.pk, ip_address=ip)
            return Response({"detail": "Two-factor authentication enabled."})

        pending_id = request.session.get("pending_2fa_user_id")
        if not pending_id:
            return Response({"detail": "No pending login."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(pk=pending_id, is_active=True).first()
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first() if user else None
        if user is None or device is None or not device.verify_token(token):
            AuditLog.log(actor=user, action="auth.2fa_verify_failed", entity_type="User", entity_id=pending_id, ip_address=ip)
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)

        del request.session["pending_2fa_user_id"]
        login(request, user)
        AuditLog.log(actor=user, action="auth.login_success", entity_type="User", entity_id=user.pk, ip_address=ip)
        return Response(UserSerializer(user).data)


class TwoFactorEnableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        device = totp.get_or_create_unconfirmed_device(request.user)
        return Response(totp.provisioning_payload(device))


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        AuditLog.log(actor=user, action="auth.logout", entity_type="User", entity_id=user.pk, ip_address=get_client_ip(request))
        logout(request)
        request.session.flush()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["current_password"]):
            return Response({"current_password": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["new_password"])
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password", "password_changed_at"])
        AuditLog.log(actor=user, action="auth.password_changed", entity_type="User", entity_id=user.pk, ip_address=get_client_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            _token, raw_token = PasswordResetToken.issue(user)
            send_mail(
                subject="IMS password reset",
                message=f"Use this token to reset your password (valid 30 minutes): {raw_token}",
                from_email=None,
                recipient_list=[user.email],
            )
            AuditLog.log(actor=user, action="auth.password_reset_requested", entity_type="User", entity_id=user.pk)
        # Always 200 -- never reveal whether the email exists.
        return Response({"detail": "If that email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_token = PasswordResetToken.verify(serializer.validated_data["token"])
        if reset_token is None:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        user = reset_token.user
        user.set_password(serializer.validated_data["new_password"])
        user.password_changed_at = timezone.now()
        user.reset_lockout()
        user.save(update_fields=["password", "password_changed_at", "failed_login_attempts", "locked_until"])
        reset_token.mark_used()
        AuditLog.log(actor=user, action="auth.password_reset_completed", entity_type="User", entity_id=user.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.ADMIN)


class UserViewSet(viewsets.ModelViewSet):
    """GET/POST /users, GET/PUT /users/{id}. Admin has full access; every
    other role may only retrieve/update their own record (self-service
    subset of fields — role/site changes go through the dedicated
    /users/{id}/role endpoint, admin-only)."""

    queryset = User.objects.all().prefetch_related("site_assignments")
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == Role.ADMIN:
            return qs
        return qs.filter(pk=self.request.user.pk)

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method == "POST" and request.user.role != Role.ADMIN:
            raise PermissionDenied("Only administrators can create users.")

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method == "PUT" and request.user.role != Role.ADMIN and obj.pk != request.user.pk:
            raise PermissionDenied("You may only update your own profile.")

    def perform_update(self, serializer):
        if self.request.user.role != Role.ADMIN:
            # Self-service: strip anything beyond the safe editable subset.
            for field in ("role", "is_active"):
                serializer.validated_data.pop(field, None)
        serializer.save()
        AuditLog.log(
            actor=self.request.user, action="user.updated", entity_type="User", entity_id=serializer.instance.pk,
        )

    def perform_create(self, serializer):
        serializer.save()
        AuditLog.log(actor=self.request.user, action="user.created", entity_type="User", entity_id=serializer.instance.pk)


class UserDeactivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = UserDeactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        override = serializer.validated_data["override"]

        blockers = services.check_pending_assets(user)
        if blockers and not override:
            return Response(
                {"detail": "User has unreturned assets or open requests.", "blockers": blockers},
                status=status.HTTP_409_CONFLICT,
            )

        user.is_active = False
        user.deactivated_at = timezone.now()
        user.deactivation_reason = reason
        user.deactivated_by = request.user
        user.save(update_fields=["is_active", "deactivated_at", "deactivation_reason", "deactivated_by"])
        AuditLog.log(
            actor=request.user, action="user.deactivated", entity_type="User", entity_id=user.pk,
            metadata={"reason": reason, "override": override, "blockers": blockers},
        )
        return Response(UserSerializer(user).data)


class UserReactivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        user.is_active = True
        user.deactivated_at = None
        user.deactivation_reason = ""
        user.deactivated_by = None
        user.save(update_fields=["is_active", "deactivated_at", "deactivation_reason", "deactivated_by"])
        AuditLog.log(actor=request.user, action="user.reactivated", entity_type="User", entity_id=user.pk)
        return Response(UserSerializer(user).data)


class UserUnlockView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        user.reset_lockout()
        AuditLog.log(actor=request.user, action="user.unlocked", entity_type="User", entity_id=user.pk)
        return Response(UserSerializer(user).data)


class UserRoleChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def put(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = UserRoleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_role = user.role
        user.role = serializer.validated_data["role"]
        user.save(update_fields=["role"])
        AuditLog.log(
            actor=request.user, action="user.role_changed", entity_type="User", entity_id=user.pk,
            metadata={"old_role": old_role, "new_role": user.role},
        )
        return Response(UserSerializer(user).data)
