"""
Reusable RBAC surface for the whole project (SRS Section 3 permission matrix).

Two concerns, always composed together, never conflated:
  - CAPABILITY: does this role have this capability at all (role-level).
  - SITE SCOPE: for capabilities tied to a specific warehouse/station/project,
    does this user's SiteAssignment cover the specific object being touched.

Every future module adds rows to ROLE_CAPABILITIES and sets `capability` /
`site_field` on its views — no new permission-class code should be needed.
"""
from rest_framework.permissions import BasePermission

# (role, action) -> True. ("<role>", "*") grants every capability for that role.
# Populated from SRS Section 3; extend additively as new modules land.
ROLE_CAPABILITIES = {
    ("admin", "*"): True,

    ("wh_supervisor", "product.view"): True,
    ("wh_supervisor", "warehouse.stock.manage"): True,
    ("wh_supervisor", "station_request.approve"): True,
    ("wh_supervisor", "station_request.view"): True,
    ("wh_supervisor", "equipment.assign"): True,
    ("wh_supervisor", "vehicle.assign"): True,
    ("wh_supervisor", "stocktake.manage"): True,
    ("wh_supervisor", "reports.view_own_site"): True,
    ("wh_supervisor", "purchase_request.create"): True,
    ("wh_supervisor", "supplier.view"): True,
    ("wh_supervisor", "purchase_order.manage"): True,

    ("station_supervisor", "product.view"): True,
    ("station_supervisor", "station_request.create"): True,
    ("station_supervisor", "station_request.view"): True,
    ("station_supervisor", "station.usage.record"): True,
    ("station_supervisor", "equipment.request"): True,
    ("station_supervisor", "vehicle.view_own"): True,
    ("station_supervisor", "stocktake.manage"): True,
    ("station_supervisor", "reports.view_own_site"): True,
    ("station_supervisor", "purchase_request.create"): True,

    ("deepclean_supervisor", "product.view"): True,
    ("deepclean_supervisor", "project.update_own"): True,
    ("deepclean_supervisor", "equipment.request"): True,
    ("deepclean_supervisor", "vehicle.request"): True,
    ("deepclean_supervisor", "reports.view_own_project"): True,
    ("deepclean_supervisor", "purchase_request.create"): True,

    ("wh_staff", "product.view"): True,
    ("wh_staff", "equipment.view_own"): True,
    ("wh_staff", "vehicle.view_own"): True,
    ("wh_staff", "stocktake.participate"): True,
    ("wh_staff", "purchase_order.manage"): True,

    ("station_staff", "product.view"): True,
    ("station_staff", "station_request.create"): True,
    ("station_staff", "station.usage.record"): True,
    ("station_staff", "equipment.view_own"): True,

    ("management", "product.view"): True,
    ("management", "station_request.view"): True,
    ("management", "equipment.view_own"): True,
    ("management", "vehicle.view_own"): True,
    ("management", "stocktake.participate"): True,
    ("management", "reports.view"): True,
    ("management", "warehouse.stock.view"): True,
    ("management", "project.view"): True,
    ("management", "supplier.view"): True,
    ("management", "purchase_order.view"): True,
}

# Roles that see everything regardless of SiteAssignment (still gated by capability).
SITE_SCOPE_EXEMPT_ROLES = {"admin", "management"}


def has_capability(user, action: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if ROLE_CAPABILITIES.get((user.role, "*")):
        return True
    return bool(ROLE_CAPABILITIES.get((user.role, action)))


def assigned_site_ids(user, site_type: str):
    """site_type is 'warehouse' or 'station' -- returns a values_list of ids
    the user is assigned to via SiteAssignment."""
    from apps.accounts.models import SiteAssignment

    field = f"{site_type}_id"
    return SiteAssignment.objects.filter(user=user, **{f"{field}__isnull": False}).values_list(field, flat=True)


def ensure_site_access(user, *, warehouse_id=None, station_id=None):
    """For action-style endpoints (stock-in/out/transfer/...) that take a
    warehouse/station id in the request body rather than as a single
    object -- raises DRF PermissionDenied if the user isn't scoped to it."""
    from rest_framework.exceptions import PermissionDenied

    if getattr(user, "role", None) in SITE_SCOPE_EXEMPT_ROLES:
        return
    if warehouse_id is not None and warehouse_id not in set(assigned_site_ids(user, "warehouse")):
        raise PermissionDenied(f"Not assigned to warehouse {warehouse_id}.")
    if station_id is not None and station_id not in set(assigned_site_ids(user, "station")):
        raise PermissionDenied(f"Not assigned to station {station_id}.")


class CapabilityPermission(BasePermission):
    """View-level gate. Set `capability = "warehouse.stock.manage"` as a class
    attribute, or `capability_map = {"GET": "...", "POST": "..."}` for
    per-method capabilities."""

    def has_permission(self, request, view):
        action = getattr(view, "capability_map", {}).get(request.method) or getattr(view, "capability", None)
        if action is None:
            return True  # view doesn't declare a capability requirement
        return has_capability(request.user, action)


class SiteScopedPermission(BasePermission):
    """Object-level gate. Views declare `site_field = "warehouse"` (the attr
    path on the object holding the related Warehouse/Station)."""

    def has_object_permission(self, request, view, obj):
        if getattr(request.user, "role", None) in SITE_SCOPE_EXEMPT_ROLES:
            return True
        site_field = getattr(view, "site_field", None)
        if not site_field:
            return True
        site_obj = getattr(obj, site_field, None)
        if site_obj is None:
            return True
        site_type = "warehouse" if site_field in ("warehouse", "source_warehouse", "dest_warehouse") else "station"
        return site_obj.pk in set(assigned_site_ids(request.user, site_type))
