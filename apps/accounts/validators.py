import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexityValidator:
    """Requires at least one uppercase, one lowercase, one digit, and one
    symbol character (SRS Section 6.3: configurable password complexity)."""

    def validate(self, password, user=None):
        errors = []
        if not re.search(r"[A-Z]", password):
            errors.append(_("Password must contain at least one uppercase letter."))
        if not re.search(r"[a-z]", password):
            errors.append(_("Password must contain at least one lowercase letter."))
        if not re.search(r"\d", password):
            errors.append(_("Password must contain at least one digit."))
        if not re.search(r"[^A-Za-z0-9]", password):
            errors.append(_("Password must contain at least one symbol."))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _("Your password must contain uppercase, lowercase, a digit, and a symbol.")
