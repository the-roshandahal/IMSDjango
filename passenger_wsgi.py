"""
Entry point cPanel's Passenger app server imports directly (via "Setup
Python App"). Not used by local dev (venv/manage.py runserver) or by any
other deployment target -- it exists only for this hosting path.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

import django  # noqa: E402

django.setup()

# Temporary: this host has no working shell access (SSH port unreachable,
# no Terminal app), so there's no way to run `bash deploy.sh` by hand.
# Running migrate/collectstatic/ensure_superuser here instead, on every
# process start, gets the app usable without one. Once real shell access
# works, switch back to deploying via deploy.sh and remove this block --
# running migrate on every worker boot is fine for a low-traffic demo, not
# something to leave in place long-term (concurrent workers cold-starting
# at once could race on the migration table; collectstatic re-scanning the
# static dir on every boot is wasted work once traffic picks up).
try:
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    call_command("collectstatic", interactive=False, verbosity=0)
    call_command("ensure_superuser", verbosity=0)
except Exception:
    import traceback

    traceback.print_exc()  # lands in stderr.log -- don't let this block the app from attempting to start

from config.wsgi import application  # noqa: E402
