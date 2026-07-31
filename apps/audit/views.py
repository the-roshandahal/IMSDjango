from django.views.generic import ListView

from apps.audit.models import AuditLog
from apps.core.mixins import CapabilityRequiredMixin


class AuditLogListView(CapabilityRequiredMixin, ListView):
    """Admin-only, full read-only trail (SRS Section 5.14 / 3: 'Full
    (read-only)' for Admin, '-' for every other role)."""

    capability = "audit.view"
    model = AuditLog
    template_name = "audit/log_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor").order_by("-timestamp")
        action = self.request.GET.get("action")
        if action:
            qs = qs.filter(action__icontains=action)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("action", "")
        return ctx
