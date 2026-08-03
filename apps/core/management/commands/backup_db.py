"""Automatic backups for hosts with no reliable shell/cron scripting beyond
"run this one command" -- cPanel's Cron Jobs feature just needs a single
python manage.py call, so all the mysqldump/tar/prune logic for both the
database and media/ uploads lives here instead of in a separate shell
script (which would also have had to safely re-parse .env's DB password).
"""
import gzip
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Dumps the database and archives media/, gzipped, then prunes backups older than --keep-days."

    def add_arguments(self, parser):
        parser.add_argument("--keep-days", type=int, default=14)

    def handle(self, *args, **options):
        backup_dir = Path(settings.BASE_DIR) / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._dump_database(backup_dir, timestamp)
        self._archive_media(backup_dir, timestamp)
        self._prune(backup_dir, options["keep_days"])

    def _dump_database(self, backup_dir, timestamp):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.mysql":
            self.stdout.write(f"Skipping DB dump -- not a MySQL database ({db['ENGINE']}).")
            return

        dump_path = backup_dir / f"db_{timestamp}.sql.gz"
        cmd = [
            "mysqldump",
            f"--host={db['HOST'] or 'localhost'}",
            f"--user={db['USER']}",
            db["NAME"],
        ]
        # MYSQL_PWD instead of --password=... so the password never shows
        # up in `ps` output on a shared host.
        env = {**os.environ, "MYSQL_PWD": db["PASSWORD"]}
        try:
            result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except FileNotFoundError as exc:
            raise CommandError("mysqldump not found on PATH -- ask your host to confirm it's available.") from exc
        except subprocess.CalledProcessError as exc:
            raise CommandError(f"mysqldump failed: {exc.stderr.decode(errors='replace')}") from exc

        with gzip.open(dump_path, "wb") as f:
            f.write(result.stdout)
        self.stdout.write(self.style.SUCCESS(f"Database backed up to {dump_path}"))

    def _archive_media(self, backup_dir, timestamp):
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists() or not any(media_root.iterdir()):
            self.stdout.write("Skipping media archive -- nothing in MEDIA_ROOT yet.")
            return

        archive_base = backup_dir / f"media_{timestamp}"
        shutil.make_archive(str(archive_base), "gztar", root_dir=media_root)
        self.stdout.write(self.style.SUCCESS(f"Media backed up to {archive_base}.tar.gz"))

    def _prune(self, backup_dir, keep_days):
        cutoff = (datetime.now() - timedelta(days=keep_days)).timestamp()
        removed = 0
        for path in backup_dir.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        if removed:
            self.stdout.write(f"Pruned {removed} backup file(s) older than {keep_days} days.")
