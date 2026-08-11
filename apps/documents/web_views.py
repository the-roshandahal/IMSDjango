from django.apps import apps as django_apps
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.core.permissions import has_capability
from apps.documents import services
from apps.documents.forms import DocumentUploadForm
from apps.documents.models import Document


def _safe_redirect_back(request):
    """Same intent as request.POST.get("next") or HTTP_REFERER, but never
    hands an attacker-controlled value straight to redirect() -- both are
    request-supplied and neither is validated by anything upstream."""
    for candidate in (request.POST.get("next"), request.META.get("HTTP_REFERER")):
        if candidate and url_has_allowed_host_and_scheme(
            candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(candidate)
    return redirect("/")

# Allowlist of what a generic attachment endpoint may attach to -- without
# this, a URL-crafted request could attach files to arbitrary models
# (e.g. User). Key is "app_label.model", matching the URL kwarg.
ATTACHABLE_MODELS = {
    "catalogue.product": "product.manage",
    "purchasing.purchaseorder": "purchase_order.manage",
    # equipment.manage/vehicle.manage are admin-only in ROLE_CAPABILITIES;
    # *.assign is what wh_supervisor actually holds day-to-day, and
    # they're the ones who'd realistically attach a service record.
    "equipment.equipment": "equipment.assign",
    "vehicles.vehicle": "vehicle.assign",
    "projects.deepcleanproject": "project.manage",
}


def _resolve_object(model_key, object_id):
    if model_key not in ATTACHABLE_MODELS:
        raise PermissionDenied("Attachments are not supported on this record type.")
    app_label, model_name = model_key.split(".")
    model_class = django_apps.get_model(app_label, model_name)
    return get_object_or_404(model_class, pk=object_id)


def _can_manage(user, model_key, obj):
    capability = ATTACHABLE_MODELS[model_key]
    if has_capability(user, capability):
        return True
    if model_key == "projects.deepcleanproject":
        return has_capability(user, "project.update_own") and obj.supervisor_id == user.id
    return False


class DocumentUploadView(LoginRequiredMixin, View):
    def post(self, request, model_key, object_id):
        obj = _resolve_object(model_key, object_id)
        if not _can_manage(request.user, model_key, obj):
            raise PermissionDenied()
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            services.attach_document(
                obj=obj, file=form.cleaned_data["file"], uploaded_by=request.user,
                description=form.cleaned_data["description"],
            )
            messages.success(request, "File attached.")
        else:
            for errors in form.errors.values():
                for e in errors:
                    messages.error(request, e)
        return _safe_redirect_back(request)


class DocumentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        model_key = f"{document.content_type.app_label}.{document.content_type.model}"
        obj = document.content_object
        if model_key not in ATTACHABLE_MODELS or not _can_manage(request.user, model_key, obj):
            raise PermissionDenied()
        document.file.delete(save=False)
        document.delete()
        messages.success(request, "Attachment removed.")
        return _safe_redirect_back(request)
