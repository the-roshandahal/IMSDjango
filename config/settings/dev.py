from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = True

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
# Reduce "database is locked" noise under light local concurrency. This is a dev-only
# convenience — the concurrency-safety of stock operations never depends on SQLite
# locking (see apps.inventory.services), so this has no bearing on correctness.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 20
