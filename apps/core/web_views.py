from django.views.generic import TemplateView


class UserGuideView(TemplateView):
    """Public (no login required) -- linked from the login page so anyone,
    including someone who hasn't been given an account yet, can read how
    the system works."""

    template_name = "core/user_guide.html"
