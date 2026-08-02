"""
Entry point cPanel's Passenger app server imports directly (via "Setup
Python App"). Not used by local dev (venv/manage.py runserver) or by any
other deployment target -- it exists only for this hosting path.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

from config.wsgi import application  # noqa: E402
