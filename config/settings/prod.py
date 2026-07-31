from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

DATABASES = {
    "default": env.db("DATABASE_URL"),  # e.g. postgres://user:pass@host:5432/ims
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
