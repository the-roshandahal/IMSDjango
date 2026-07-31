from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import PasswordResetToken, SiteAssignment, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "is_active", "is_2fa_enabled", "is_locked")
    list_filter = ("role", "is_active", "is_2fa_enabled")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "IMS profile",
            {
                "fields": (
                    "role", "phone", "failed_login_attempts", "locked_until", "is_2fa_enabled",
                    "deactivated_at", "deactivation_reason", "deactivated_by", "password_changed_at",
                )
            },
        ),
    )


@admin.register(SiteAssignment)
class SiteAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "warehouse", "station", "assigned_at")
    list_filter = ("warehouse", "station")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    readonly_fields = [f.name for f in PasswordResetToken._meta.fields]

    def has_add_permission(self, request):
        return False
