# Deploying to cPanel

Same as what you've done before: create the Python app, clone the repo,
SSH in, install requirements, done. Only two things this project adds on
top of that habit, both one-time:

- A `.env` file for secrets (your repo is **public** on GitHub, so real
  passwords can never sit in a tracked file — this is the one thing not
  worth simplifying away).
- Two extra one-line commands after `pip install` (`migrate` and
  `collectstatic`) — Django-specific, not optional, but still just commands
  you type once per deploy, same as before.

No `.cpanel.yml`, no "Deploy" button, no dashboard automation. Just SSH.

**Currently blocked on SSH working** (port 22/2222 both unreachable,
waiting on hosting support to confirm the right port) — see **No-SSH
fallback** near the bottom for how the app is running right now instead.
Switch back to the steps below once SSH is confirmed working.

---

## One-time setup

### 1. Python App (if not already done)

cPanel → **Setup Python App** → **Create Application** → Application root
`cleantech`, on your main domain `roshandahal.com.au` (not the `cleantech`
subdomain — that's where Python wasn't working), startup file
`passenger_wsgi.py`, entry point `application`. This gives you a venv —
note the `source .../activate` line it shows you.

### 2. Clean slate — remove whatever's currently there

You've had a few false starts (wrong domain, `.cpanel.yml` edits, the
subdomain attempt) — easiest to wipe and start clean rather than untangle
it. If you still have the old `ims` app/repo from the subdomain attempt,
delete that too (Setup Python App → remove that application; Git Version
Control → remove that repo) so it's not confused with this one.

- cPanel → **Git Version Control** → the `cleantech` repo (if it already
  exists from a prior attempt) → **Manage** → **Delete** (this only removes
  the git tracking + local files, not your Python App or database).
- File Manager → confirm the `cleantech` folder is empty (delete anything
  left over, e.g. a stray `passenger_wsgi.py` stub).

### 3. Clone

cPanel → **Git Version Control** → **Create**:
- Clone URL: `https://github.com/the-roshandahal/IMSDjango.git`
- Repository Path: `/home/roshanda/cleantech`
- Click **Create**.

### 4. Create `.env`

File Manager → `cleantech` → **+ File** → name it `.env` → **Edit**, paste:

```
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<generate one, see below>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=roshandahal.com.au,www.roshandahal.com.au
DATABASE_URL=mysql://roshanda_cleantech:<url-encoded db password>@localhost:3306/roshanda_cleantech

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=ion.quantumcore.com.au
EMAIL_PORT=465
EMAIL_USE_TLS=False
EMAIL_USE_SSL=True
EMAIL_HOST_USER=info@roshandahal.com.au
EMAIL_HOST_PASSWORD=<the info@ mailbox password>
DEFAULT_FROM_EMAIL=info@roshandahal.com.au

DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=info@roshandahal.com.au
DJANGO_SUPERUSER_PASSWORD=<pick a strong password for your first login>

SESSION_INACTIVITY_TIMEOUT_SECONDS=1800
PASSWORD_RESET_TOKEN_TTL_MINUTES=30
ACCOUNT_LOCKOUT_THRESHOLD=5
ACCOUNT_LOCKOUT_COOLDOWN_MINUTES=15
PASSWORD_MAX_AGE_DAYS=90
```

`DJANGO_ALLOWED_HOSTS` assumes the site serves from the bare main domain —
adjust if it should actually be reachable at a different hostname. Every
secret above is a placeholder on purpose, since this file is tracked in a
**public** repo — generate a real `DJANGO_SECRET_KEY` with:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

and pull the real, percent-encoded `DATABASE_URL` value and the mailbox
password from your own private notes (cPanel → MySQL Databases / Email
Accounts if you need to reset either).
`EMAIL_HOST` is carried over from the earlier mailbox, on the assumption
`info@roshandahal.com.au` sits on the same mail server (same hosting
account) — check **Email Accounts → Connect Devices** for this new mailbox
if mail doesn't send, in case that assumption is wrong.

`DJANGO_SUPERUSER_*` creates your first login automatically the first time
you deploy (next step) — no interactive prompt needed, but also nothing
extra you have to think about.

### 5. SSH in and deploy

From PowerShell:

```
ssh roshanda@roshandahal.com.au
```

If that doesn't resolve, check cPanel's **SSH Access** page for the exact
host/port to use instead.

Enter your cPanel password when prompted. Then:

```
cd ~/cleantech
bash deploy.sh
```

This installs `requirements/prod.txt`, runs migrations, collects static
files, creates your admin login, and restarts the app.

### 6. Check it's live

Visit your domain. Log in with the `DJANGO_SUPERUSER_USERNAME`/`PASSWORD`
from step 4, at `/login/`.

---

## Every update after this

```
git push          # on your dev machine, as usual
```

then, over SSH:

```
cd ~/cleantech
git pull
bash deploy.sh
```

Three commands, every time. That's it.

---

## Optional: auto-deploy on every push (no manual SSH step)

If you'd rather not SSH in after every push, `auto-deploy.sh` (repo root)
does the `git pull` + `bash deploy.sh` step for you, on a schedule, and
only actually deploys when there's something new to pull -- a quiet tick
does nothing and sends no email.

**One-time setup**, cPanel → **Cron Jobs** → **Add New Cron Job**:
- Command: `bash /home/roshanda/cleantech/auto-deploy.sh`
- Schedule: every 5–10 minutes is plenty (`*/10 * * * *`, or the Common
  Settings dropdown).

From then on, `git push` on your dev machine is the only step -- the next
cron tick (within your chosen interval) picks it up, pulls, and redeploys.
Check `tmp/auto-deploy.log` in the repo (via File Manager, or `tail` over
SSH) for a history of what it's actually deployed and when. cPanel will
also email you directly if a deploy fails (a quiet/no-op tick produces no
email, only a real deploy or a failure does).

This is a convenience layer on top of the manual flow above, not a
replacement for understanding it -- if `auto-deploy.sh` ever misbehaves,
the manual `git pull && bash deploy.sh` steps always still work exactly
as documented.

---

## Why `.env` can't just be skipped

Your GitHub repo is public. Anything in a tracked file is visible to
anyone, forever (even after you later delete it, it's still in the git
history). `.env` is `.gitignore`d — it's created once, by hand, directly on
the server, and `git pull` never touches it again no matter how many times
you deploy. That's the only piece of ceremony this setup has that your old
projects probably didn't — everything else is the same habit you already
have.

---

## No-SSH fallback (temporary)

While SSH is unreachable, `passenger_wsgi.py` runs `migrate`,
`collectstatic`, and `ensure_superuser` itself, automatically, every time
the app process starts — so the site can come up usable without ever
running `deploy.sh` by hand. The one thing that still can't happen without
some form of shell is installing the Python packages themselves
(`pip install`) — cPanel's Setup Python App page can do that part through
its own UI though, no SSH needed:

1. Make sure `.env` already exists in `~/cleantech` (Part 4 above).
2. cPanel → **Git Version Control** → clone/pull this repo into
   `/home/roshanda/cleantech` if you haven't already (Parts 2–3 above still
   apply — cloning itself doesn't need SSH).
3. cPanel → **Setup Python App** → click into the `cleantech` app.
4. Find the **requirements.txt** field on that page (it's part of the app's
   configuration, usually right below the venv info) and set it to
   `requirements.txt` (a root-level file already in the repo, just points
   at `requirements/prod.txt` — added so this field has something
   standard-looking to find regardless of what path format the field
   expects).
5. Click whatever button installs it — usually labeled **Run Pip Install**
   or similar, right next to that field.
6. On the same page, click **Restart** (every Setup Python App page has
   one). This is what actually triggers `passenger_wsgi.py`, and with it,
   the migrate/collectstatic/superuser-creation block.
7. Visit your domain. If it's still a 500, check `stderr.log` via File
   Manager (Part 6's troubleshooting note higher up) — most likely cause at
   this point is the `pip install` step not actually completing, since
   everything downstream depends on those packages being present.

**This is a temporary shortcut, not how this should run long-term** — doing
migrate/collectstatic on every process boot is wasted work once there's
real traffic, and if cPanel ever spins up multiple worker processes at
once on a cold start, they could theoretically race on the migrations
table. Once SSH is confirmed working (ask your host for the exact
host/port), the plan is: revert `passenger_wsgi.py` to just importing
`config.wsgi.application` (drop the `django.setup()` +
`call_command(...)` block), delete the root `requirements.txt` shim, and
go back to the plain `bash deploy.sh` flow in the main steps above, which
only runs those commands once per actual deploy instead of once per
process start.
