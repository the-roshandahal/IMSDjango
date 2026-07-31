from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import Role, SiteAssignment, User


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # email or username
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class TwoFactorVerifySerializer(serializers.Serializer):
    token = serializers.CharField(max_length=12)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value, user=self.context["request"].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class SiteAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteAssignment
        fields = ["id", "warehouse", "station", "assigned_at"]
        read_only_fields = ["id", "assigned_at"]


class UserSerializer(serializers.ModelSerializer):
    site_assignments = SiteAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "phone",
            "role", "is_active", "is_2fa_enabled", "deactivated_at",
            "deactivation_reason", "date_joined", "site_assignments",
        ]
        read_only_fields = [
            "id", "is_active", "is_2fa_enabled", "deactivated_at",
            "deactivation_reason", "date_joined", "site_assignments",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    # role is blank=True on the model (deactivated/system accounts may end
    # up role-less), but required at creation time -- blank means zero RBAC
    # capabilities.
    role = serializers.ChoiceField(choices=Role.choices)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone", "role", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_role(self, value):
        if value not in Role.values:
            raise serializers.ValidationError("Invalid role.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserRoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class UserDeactivateSerializer(serializers.Serializer):
    reason = serializers.CharField()
    override = serializers.BooleanField(default=False)
