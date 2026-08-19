from django.http import Http404
from django.views.generic import TemplateView

from apps.core.case_studies import get_adjacent_case_studies, get_case_study


class ServiceWorkerView(TemplateView):
    """Served at /sw.js (not /static/sw.js) so the default registration
    scope covers the whole site, not just /static/. Rendered as a Django
    template so {% static %} inside it resolves to whitenoise's hashed
    filenames in prod. Cache-Control: no-cache forces the browser to
    revalidate on every check instead of trusting its own HTTP cache on
    top of the service worker update algorithm."""

    template_name = "sw.js"
    content_type = "application/javascript"

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        response["Cache-Control"] = "no-cache"
        response["Service-Worker-Allowed"] = "/"
        return response


class ManifestView(TemplateView):
    """Web app manifest, served as a template (not a plain static file)
    so icon URLs go through {% static %} and stay correct under
    whitenoise's hashed filenames in prod."""

    template_name = "manifest.json"
    content_type = "application/manifest+json"


class OfflineView(TemplateView):
    """Self-contained fallback the service worker serves for navigations
    that fail with no cached copy of the requested page -- must not pull
    in app.css or fonts, since the whole point is it still renders with
    no network."""

    template_name = "offline.html"


class UserGuideView(TemplateView):
    """Public (no login required) -- linked from the login page so anyone,
    including someone who hasn't been given an account yet, can read how
    the system works."""

    template_name = "core/user_guide.html"


class CaseStudyDetailView(TemplateView):
    """Public marketing page, one per case study, linked from the homepage carousel."""

    template_name = "core/case_study_detail.html"

    def get_context_data(self, **kwargs):
        case_study = get_case_study(kwargs["slug"])
        if case_study is None:
            raise Http404("Case study not found")
        ctx = super().get_context_data(**kwargs)
        ctx["case_study"] = case_study
        ctx["prev_case_study"], ctx["next_case_study"] = get_adjacent_case_studies(kwargs["slug"])
        return ctx
