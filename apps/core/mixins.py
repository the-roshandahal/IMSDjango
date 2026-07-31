from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.core.permissions import assigned_site_ids, has_capability

SITE_SCOPE_EXEMPT_ROLES = {"admin", "management"}


class CapabilityRequiredMixin(LoginRequiredMixin):
    """Server-rendered-view equivalent of CapabilityPermission."""

    capability = None

    def dispatch(self, request, *args, **kwargs):
        if self.capability and not has_capability(request.user, self.capability):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class SiteScopedQuerysetMixin:
    """Server-rendered-view equivalent of SiteScopedPermission's queryset
    pre-filtering. `site_field` is the FK attribute name on the model, e.g.
    'warehouse' or 'station'. `site_type` is 'warehouse' or 'station'."""

    site_field = None
    site_type = "warehouse"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", None) in SITE_SCOPE_EXEMPT_ROLES or not self.site_field:
            return qs
        ids = list(assigned_site_ids(user, self.site_type))
        return qs.filter(**{f"{self.site_field}_id__in": ids})
