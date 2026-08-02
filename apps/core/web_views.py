from django.http import Http404
from django.views.generic import TemplateView

from apps.core.case_studies import get_adjacent_case_studies, get_case_study


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
