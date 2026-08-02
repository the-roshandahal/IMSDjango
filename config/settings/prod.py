from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, env

DEBUG = False

DATABASES = {
    "default": env.db("DATABASE_URL"),  # e.g. mysql://user:pass@localhost:3306/ims
}

# Serve collected static files directly from the app process -- shared cPanel
# hosting doesn't give you an easy way to point Apache at STATIC_ROOT, so
# whitenoise does it instead. Must sit right after SecurityMiddleware.
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
