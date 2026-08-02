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
DJANGO_SECRET_KEY=+dzni)zkozhbrjr2q#ba6=u@3w%vn%f!^7k^xxcisj64yd+m4a
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
adjust if it should actually be reachable at a different hostname. Passwords
are placeholders here on purpose (see note in this repo's history about why)
— pull the real, percent-encoded `DATABASE_URL` value from your own private
notes, and the mailbox password from wherever you saved it.
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

## Why `.env` can't just be skipped

Your GitHub repo is public. Anything in a tracked file is visible to
anyone, forever (even after you later delete it, it's still in the git
history). `.env` is `.gitignore`d — it's created once, by hand, directly on
the server, and `git pull` never touches it again no matter how many times
you deploy. That's the only piece of ceremony this setup has that your old
projects probably didn't — everything else is the same habit you already
have.
