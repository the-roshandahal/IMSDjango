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
    ("wh_supervisor", "warehouse.view"): True,
    ("wh_supervisor", "warehouse.stock.manage"): True,
    ("wh_supervisor", "station_request.approve"): True,
    ("wh_supervisor", "station_request.view"): True,
    ("wh_supervisor", "equipment.assign"): True,
    ("wh_supervisor", "equipment.view_own"): True,
    ("wh_supervisor", "vehicle.assign"): True,
    ("wh_supervisor", "vehicle.view_own"): True,
    ("wh_supervisor", "stocktake.manage"): True,
    ("wh_supervisor", "reports.view_own_site"): True,
    ("wh_supervisor", "purchase_request.create"): True,
    ("wh_supervisor", "supplier.view"): True,
    ("wh_supervisor", "purchase_order.manage"): True,
    ("wh_supervisor", "employee.manage"): True,
    ("wh_supervisor", "employee.view"): True,
    # Merged in from the retired "management" role -- one person runs the
    # whole warehouse side now, so they get the company-wide oversight
    # view management used to have, not just their own site.
    ("wh_supervisor", "reports.view"): True,
    ("wh_supervisor", "warehouse.stock.view"): True,
    ("wh_supervisor", "project.view"): True,
    ("wh_supervisor", "stocktake.participate"): True,
    ("wh_supervisor", "hazard.report"): True,
    ("wh_supervisor", "hazard.view"): True,
    ("wh_supervisor", "hazard.manage"): True,
    ("wh_supervisor", "attendance.duty_sheet.manage"): True,
    ("wh_supervisor", "attendance.view"): True,

    ("station_supervisor", "product.view"): True,
    ("station_supervisor", "station_request.create"): True,
    ("station_supervisor", "station_request.view"): True,
    ("station_supervisor", "station.usage.record"): True,
    ("station_supervisor", "equipment.request"): True,
    ("station_supervisor", "equipment.view_own"): True,
    ("station_supervisor", "vehicle.view_own"): True,
    ("station_supervisor", "stocktake.manage"): True,
    ("station_supervisor", "reports.view_own_site"): True,
    ("station_supervisor", "purchase_request.create"): True,
    ("station_supervisor", "transaction.view"): True,
    ("station_supervisor", "hazard.report"): True,
    ("station_supervisor", "hazard.view"): True,
    ("station_supervisor", "hazard.manage"): True,
    ("station_supervisor", "attendance.duty_sheet.manage"): True,
    ("station_supervisor", "attendance.view"): True,
    ("station_supervisor", "attendance.clock"): True,

    ("deepclean_supervisor", "product.view"): True,
    ("deepclean_supervisor", "project.update_own"): True,
    ("deepclean_supervisor", "equipment.request"): True,
    ("deepclean_supervisor", "vehicle.request"): True,
    ("deepclean_supervisor", "reports.view_own_project"): True,
    ("deepclean_supervisor", "purchase_request.create"): True,
    ("deepclean_supervisor", "employee.manage"): True,
    ("deepclean_supervisor", "employee.view"): True,
    ("deepclean_supervisor", "hazard.report"): True,
    ("deepclean_supervisor", "hazard.view"): True,
    ("deepclean_supervisor", "hazard.manage"): True,

    ("wh_staff", "product.view"): True,
    ("wh_staff", "warehouse.view"): True,
    ("wh_staff", "equipment.view_own"): True,
    ("wh_staff", "vehicle.view_own"): True,
    ("wh_staff", "stocktake.participate"): True,
    ("wh_staff", "stocktake.manage"): True,
    ("wh_staff", "purchase_order.manage"): True,
    ("wh_staff", "hazard.report"): True,
    ("wh_staff", "hazard.view"): True,

    ("station_staff", "product.view"): True,
    ("station_staff", "station_request.create"): True,
    ("station_staff", "station.usage.record"): True,
    ("station_staff", "equipment.view_own"): True,
    ("station_staff", "stocktake.manage"): True,
    ("station_staff", "transaction.view"): True,
    ("station_staff", "hazard.report"): True,
    ("station_staff", "hazard.view"): True,
    ("station_staff", "attendance.clock"): True,
}

# Roles that see everything regardless of SiteAssignment (still gated by capability).
# wh_supervisor is exempt too -- with the "management" role retired, they're
# the sole company-wide oversight role now (see the capability grants above).
SITE_SCOPE_EXEMPT_ROLES = {"admin", "wh_supervisor"}

# Every capability string used anywhere in the app, grouped for the "custom
# permissions" checklist on a user's profile. Keep this in sync when a new
# capability is introduced -- nothing breaks if it's missed (has_capability
# still works), it just won't be toggleable from the checklist UI.
CAPABILITY_CATALOG = [
    ("Products", [
        ("product.view", "View products"),
        ("product.manage", "Create/edit/archive products"),
    ]),
    ("Warehouses", [
        ("warehouse.view", "View warehouses"),
        ("warehouse.manage", "Create/edit warehouses"),
        ("warehouse.stock.manage", "Record stock movements (in/out/transfer/adjust)"),
        ("warehouse.stock.view", "View warehouse stock levels"),
    ]),
    ("Stations & Requests", [
        ("station_request.view", "View stock requests"),
        ("station_request.create", "Raise a stock request"),
        ("station_request.approve", "Approve/reject stock requests"),
        ("station.usage.record", "Record daily station chemical usage"),
    ]),
    ("Stocktakes", [
        ("stocktake.manage", "Run a stocktake / weekly stock audit"),
        ("stocktake.view", "View stocktake history"),
        ("stocktake.participate", "Take part in a stocktake"),
    ]),
    ("Transactions", [
        ("transaction.view", "View the transaction/movement history"),
    ]),
    ("Equipment", [
        ("equipment.view_own", "View equipment"),
        ("equipment.assign", "Assign/release/maintain equipment"),
        ("equipment.manage", "Create/edit equipment records"),
        ("equipment.request", "Request equipment"),
    ]),
    ("Vehicles", [
        ("vehicle.view_own", "View vehicles"),
        ("vehicle.assign", "Assign/release/maintain vehicles"),
        ("vehicle.manage", "Create/edit vehicle records"),
        ("vehicle.request", "Request a vehicle"),
    ]),
    ("Deep Clean Projects", [
        ("project.view", "View all deep clean projects"),
        ("project.manage", "Create/manage any deep clean project"),
        ("project.update_own", "Manage projects you supervise"),
    ]),
    ("Employees", [
        ("employee.view", "View the employee directory"),
        ("employee.manage", "Add/edit employees, toolbox talks"),
    ]),
    ("Hazard & Incident Reports", [
        ("hazard.report", "Report a hazard, near miss or incident"),
        ("hazard.view", "View hazard/incident reports for your site"),
        ("hazard.manage", "Investigate, assign and close out reports"),
    ]),
    ("Attendance & Duty Sheets", [
        ("attendance.clock", "Clock in/out and complete duty sheet tasks (self-service)"),
        ("attendance.duty_sheet.manage", "Manage duty sheets and their assignment to employees"),
        ("attendance.view", "View clock-in history and duty sheet completion across stations"),
    ]),
    ("Suppliers & Purchasing", [
        ("supplier.view", "View suppliers"),
        ("supplier.manage", "Create/edit suppliers"),
        ("purchase_order.view", "View purchase orders"),
        ("purchase_order.manage", "Create/send/receive purchase orders"),
        ("purchase_request.create", "Request a purchase"),
    ]),
    ("Reports", [
        ("reports.view", "View all reports"),
        ("reports.view_own_site", "View reports for your own site"),
        ("reports.view_own_project", "View reports for your own projects"),
    ]),
    ("Administration", [
        ("user.manage", "Manage user accounts and permissions"),
        ("audit.view", "View the audit log"),
    ]),
]


def _user_overrides(user):
    """Active (non-expired) per-user capability overrides, cached on the
    user instance for the life of the request -- has_capability() is
    called many times per page, this keeps it to one query per request."""
    if not hasattr(user, "_capability_overrides_cache"):
        from django.db.models import Q
        from django.utils import timezone

        from apps.accounts.models import UserCapabilityOverride

        rows = UserCapabilityOverride.objects.filter(user=user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        user._capability_overrides_cache = {row.capability: row.granted for row in rows}
    return user._capability_overrides_cache


def has_capability(user, action: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    overrides = _user_overrides(user)
    if action in overrides:
        return overrides[action]
    if ROLE_CAPABILITIES.get((user.role, "*")):
        return True
    return bool(ROLE_CAPABILITIES.get((user.role, action)))


def role_default_capability(role: str, action: str) -> bool:
    """The role's baseline, ignoring any per-user override -- used by the
    checklist UI to show what's inherited vs explicitly overridden."""
    if ROLE_CAPABILITIES.get((role, "*")):
        return True
    return bool(ROLE_CAPABILITIES.get((role, action)))


def effective_capabilities(user) -> dict:
    """{capability: bool} for every capability in CAPABILITY_CATALOG,
    merging the user's role default with any active override."""
    overrides = _user_overrides(user)
    result = {}
    for _group, items in CAPABILITY_CATALOG:
        for capability, _label in items:
            result[capability] = overrides.get(capability, role_default_capability(user.role, capability))
    return result


def set_capability_overrides(*, user, grants: dict, granted_by, expires_at=None, reason=""):
    """`grants` is {capability: bool} for every capability being set from
    the checklist. Only persists a row where the desired state actually
    differs from the role default -- ticking a box the role already has
    isn't an "override", it's just the default, so no row is created (and
    an existing override matching the default is removed)."""
    from apps.accounts.models import UserCapabilityOverride

    changed = []
    for capability, desired in grants.items():
        default = role_default_capability(user.role, capability)
        existing = UserCapabilityOverride.objects.filter(user=user, capability=capability).first()
        if desired == default:
            if existing:
                existing.delete()
                changed.append((capability, "cleared"))
            continue
        if existing and existing.granted == desired and existing.expires_at == expires_at:
            continue
        UserCapabilityOverride.objects.update_or_create(
            user=user, capability=capability,
            defaults={"granted": desired, "granted_by": granted_by, "expires_at": expires_at, "reason": reason},
        )
        changed.append((capability, "granted" if desired else "revoked"))
    return changed


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
