"""Non-interactive, idempotent superuser creation -- for hosts (like cPanel
without Terminal/SSH) where `createsuperuser`'s interactive prompts can't be
run. Reads DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD from the environment.
Safe to run on every deploy: no-ops once that username already exists.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates a superuser from DJANGO_SUPERUSER_* env vars if that username doesn't already exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD not set -- skipping.")
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User '{username}' already exists -- skipping.")
            return

        User.objects.create_superuser(username=username, email=email or "", password=password, role="admin")
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
