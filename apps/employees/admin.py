from django.contrib import admin

from apps.employees.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "phone", "position", "is_active", "profile_complete"]
    list_filter = ["is_active", "position"]
    search_fields = ["first_name", "last_name", "email", "phone", "riw_number"]
