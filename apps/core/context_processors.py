from apps.accounts.models import Role
from apps.core.permissions import has_capability


def nav_capabilities(request):
    """Exposes capability flags to every template so the sidebar/nav can
    show only what the signed-in role can actually use, without every
    template re-deriving RBAC logic."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    return {
        "can_view_products": has_capability(user, "product.view"),
        "can_manage_products": has_capability(user, "product.manage"),
        "can_manage_stock": has_capability(user, "warehouse.stock.manage"),
        "can_record_usage": has_capability(user, "station.usage.record"),
        "can_manage_stocktake": has_capability(user, "stocktake.manage"),
        "can_view_requests": has_capability(user, "station_request.view"),
        "can_create_requests": has_capability(user, "station_request.create"),
        "can_approve_requests": has_capability(user, "station_request.approve"),
        # "*.request" capabilities (station/deepclean supervisors) aren't
        # wired to a page yet -- no equipment/vehicle request-approval flow
        # exists (deliberately out of scope this pass, see commit notes).
        # Only show the nav link where there's a real page behind it.
        "can_view_equipment": has_capability(user, "equipment.view_own") or has_capability(user, "equipment.assign"),
        "can_view_vehicles": has_capability(user, "vehicle.view_own") or has_capability(user, "vehicle.assign"),
        "can_view_projects": has_capability(user, "project.manage")
        or has_capability(user, "project.view")
        or has_capability(user, "project.update_own"),
        "can_view_suppliers": has_capability(user, "supplier.view") or has_capability(user, "supplier.manage"),
        "can_view_purchase_orders": has_capability(user, "purchase_order.view")
        or has_capability(user, "purchase_order.manage"),
        "is_admin": user.role == Role.ADMIN,
    }
