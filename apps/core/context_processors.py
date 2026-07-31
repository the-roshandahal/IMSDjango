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
        "is_admin": user.role == Role.ADMIN,
    }
