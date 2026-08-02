# Deploying to cPanel — full click-by-click walkthrough

This is written for this exact deployment: domain `cleantech.roshandahal.com.np`,
database `roshanda_cleantech`, mailbox `noreply@cleantech.roshandahal.com.np`.
Wherever you see `roshanda`, that's your cPanel login username (shown
top-right of the cPanel screen after you log in) — swap it in everywhere.

No password appears in this file. Every place a secret is needed, it says
"paste from your notes" — keep the actual values only in the `.env` file you
create directly on the server (step 4) and nowhere else.

Tip used throughout: cPanel has a **search box at the top of the page**
("Find a feature quickly..."). Typing a feature's name there and clicking the
icon that appears is faster and more reliable than hunting through menus,
since menu layout differs by host/theme. Every step below tells you what to
type into that box.

---

## Where you already are

- ✅ Database `roshanda_cleantech` created
- ✅ Database user `roshanda_cleantech` created (you gave me its password)
- ✅ Mailbox `noreply@cleantech.roshandahal.com.np` created (you gave me its
  password and SMTP details)
- ⬜ Database user not yet confirmed linked to the database with privileges
- ⬜ Repository not yet cloned
- ⬜ Python App not yet set up
- ⬜ `.env` not yet created on the server
- ⬜ Nothing deployed yet

**No Terminal on this host** — every step below is written to work entirely
through the cPanel web UI (File Manager + Git Version Control's own
"Deploy" button, which runs shell commands on the server for you, with no
terminal window needed on your end). If you ever do get Terminal or SSH
access later, the `bash deploy.sh` alternative mentioned at the bottom still
works too.

Start at Part 1.

---

## Part 1 — Confirm the database user has privileges

Easy to create both a database and a user and forget to actually link them —
worth 30 seconds to check now rather than debugging a mystery "access denied"
error later.

1. In cPanel, type `MySQL Databases` into the search box, click the result.
2. Scroll down to the **Current Databases** section.
3. Find the row for `roshanda_cleantech`. It should list `roshanda_cleantech`
   as a user underneath it, with **ALL PRIVILEGES**.
4. If the user is **not** listed there: scroll up to **Add User To Database**,
   select User = `roshanda_cleantech`, Database = `roshanda_cleantech`, click
   **Add**. On the next screen, check **ALL PRIVILEGES**, click
   **Make Changes**.

---

## Part 2 — Clone the repository

1. In cPanel, type `Git Version Control` into the search box, click the result.
2. Click **Create**.
3. Fill in:
   - **Clone URL**: `https://github.com/the-roshandahal/IMSDjango.git`
   - **Repository Path**: `/home/roshanda/ims`
     (This field usually auto-fills based on the repo name — clear it and
     type the full path if it doesn't. It must be a path that **doesn't
     already exist**, or is completely empty.)
   - Leave **Clone the repository** checked (it's checked by default) — this
     downloads the actual files, not just a bare repo reference.
4. Click **Create**.
5. Wait for the "Repository was successfully cloned" confirmation. This can
   take 10–30 seconds.
6. Click **Manage** on the new repo row, confirm the branch shown is `main`.

You now have all the project files (including `passenger_wsgi.py`,
`deploy.sh`, `.cpanel.yml`) sitting at `/home/roshanda/ims`.

---

## Part 3 — Set up the Python App

1. In cPanel, type `Setup Python App` into the search box, click the result.
2. Click **Create Application**.
3. Fill in:
   - **Python version**: pick the highest 3.13.x.
   - **Application root**: `ims`
     (relative to your home directory — resolves to
     `/home/roshanda/ims`, the exact folder from Part 2. This
     **must** match exactly.)
   - **Application URL**: select `cleantech.roshandahal.com.np` from the
     domain dropdown. Leave the path portion blank (serve from the domain
     root, not a sub-path).
   - **Application startup file**: `passenger_wsgi.py`
   - **Application Entry point**: `application`
4. Click **Create**.
5. The app detail page reloads showing a virtualenv path and a line similar
   to:
   ```
   source /home/roshanda/virtualenv/ims/3.13/bin/activate
   ```
   **Copy this exact line somewhere safe (Notepad etc.) — you need it in
   Part 5.**
6. Still on this page, scroll to **Configuration files** /
   **Environment variables** section — you can ignore this; we're using a
   `.env` file instead (Part 4), which the app already reads on its own.

---

## Part 4 — Create `.env` on the server

1. In cPanel, type `File Manager` into the search box, click the result.
2. Navigate into `ims` (double-click the folder). You should see the
   project files: `manage.py`, `apps`, `config`, `passenger_wsgi.py`, etc.
   If you don't see hidden-file-looking things and wonder where `.env`
   should go — this is the same folder, `.env` just doesn't exist yet.
3. Click **+ File** in the top toolbar. Name it exactly `.env`
   (including the leading dot). Click **Create New File**.
4. Right-click the new `.env` file → **Edit** (or select it and click
   **Edit** in the toolbar). Confirm the "Encoding" popup with **Edit**.
5. Paste the following, then fill in the two `<...>` placeholders using the
   secrets you already have on hand (the ones you sent me earlier in this
   conversation):

   ```
   DJANGO_SETTINGS_MODULE=config.settings.prod
   DJANGO_SECRET_KEY=+dzni)zkozhbrjr2q#ba6=u@3w%vn%f!^7k^xxcisj64yd+m4a
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=cleantech.roshandahal.com.np
   DATABASE_URL=mysql://roshanda_cleantech:<url-encoded db password>@localhost:3306/roshanda_cleantech

   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=ion.quantumcore.com.au
   EMAIL_PORT=465
   EMAIL_USE_TLS=False
   EMAIL_USE_SSL=True
   EMAIL_HOST_USER=noreply@cleantech.roshandahal.com.np
   EMAIL_HOST_PASSWORD=<paste the mailbox password>
   DEFAULT_FROM_EMAIL=noreply@cleantech.roshandahal.com.np

   DJANGO_SUPERUSER_USERNAME=admin
   DJANGO_SUPERUSER_EMAIL=noreply@cleantech.roshandahal.com.np
   DJANGO_SUPERUSER_PASSWORD=<pick a strong password for your first login>

   SESSION_INACTIVITY_TIMEOUT_SECONDS=1800
   PASSWORD_RESET_TOKEN_TTL_MINUTES=30
   ACCOUNT_LOCKOUT_THRESHOLD=5
   ACCOUNT_LOCKOUT_COOLDOWN_MINUTES=15
   PASSWORD_MAX_AGE_DAYS=90
   ```

   The `DJANGO_SECRET_KEY` above is a real, randomly generated key — safe to
   use as-is, it doesn't need to be your own. The database password needs
   its special characters percent-encoded to be valid inside a URL — I
   already did this for you earlier in our chat (look back for the
   `DATABASE_URL=mysql://roshanda_cleantech:%5D...` line and copy that exact
   value rather than retyping the raw password here). The
   `DJANGO_SUPERUSER_*` lines create your first admin login automatically on
   the next deploy (Part 6) — no Terminal needed for that step at all. Pick
   any username/password you'll remember.
6. Click **Save Changes** (top right of the editor).
7. Close the editor tab.

---

## Part 5 — Fix the placeholder venv paths

Already done — `.cpanel.yml` and `deploy.sh` in the repo now both point at
`/home/roshanda/virtualenv/ims/3.13/bin/activate`, the real line from your
Part 3, step 5. Once this gets pushed and you pull it (Part 6, step 1
below), nothing further is needed here.

---

## Part 6 — First deploy

1. In cPanel, type `Git Version Control` into the search box, click the result.
2. Click **Manage** on the `ims` repository.
3. Click the **Pull or Deploy** tab.
4. Click **Update from Remote** — pulls in the real venv path from Part 5.
5. Click **Deploy HEAD Commit**.

This runs every task in `.cpanel.yml` on the server: installs everything in
`requirements/prod.txt` (Django, PyMySQL, whitenoise, gunicorn), applies
every database migration, collects static files, creates your admin login
from the `DJANGO_SUPERUSER_*` values in Part 4, and restarts the app —
entirely through this button, no Terminal involved.

Watch the output panel that appears — each task shows its own output. If a
step fails, see **Troubleshooting** below.

---

## Part 7 — Check it's live

Visit `https://cleantech.roshandahal.com.np` in a browser. You should see the
public homepage. Log in with the `DJANGO_SUPERUSER_USERNAME`/`PASSWORD` you
set in Part 4 (created automatically during Part 6's deploy) at `/login/`.

If you get a 500 error, see **Troubleshooting**.

---

## Every update after this (the normal workflow)

Once the above is done, deploying a change is two clicks:

1. On your dev machine: `git push` to `main` on GitHub, as usual.
2. In cPanel: **Git Version Control** → this repo → **Manage** →
   **Pull or Deploy** tab → click **Update from Remote** (this is `git pull`).
3. Click **Deploy HEAD Commit**. This automatically runs everything in
   `.cpanel.yml` — reinstalls any changed packages, runs any new migrations,
   re-collects static files, restarts the app. No Terminal needed.

If you prefer doing it by hand, Terminal works too:
```
cd /home/roshanda/ims
git pull
bash deploy.sh
```

Either way runs the same four things: install deps, migrate, collectstatic,
restart. **That's what makes pulling safe** — a migration that only exists
in a brand-new commit gets applied automatically before Passenger starts
serving that commit's code, so you never end up with new code running
against an old database schema.

---

## Do you need a separate `.gitignore` on cPanel?

No. `.gitignore` is itself a tracked file — it comes along with every clone
and pull automatically. You never create or edit a second copy on the
server.

What it deliberately excludes from git — `.env`, `media/`, `staticfiles/`,
`venv/` — are exactly the files that must differ between your laptop and the
server, or that get rebuilt on the server itself:

- **`.env`** — real secrets and the production database URL live only on
  the server (Part 4). `git pull` never touches a file that was never
  tracked in the first place, so this is safe no matter how many times you
  pull.
- **`media/`** — uploaded photos (hazard reports, employee photos, etc.)
  exist only on the server's disk. Git doesn't know about them, so it can't
  delete or overwrite them on pull. Back this up yourself periodically
  (cPanel's Backup Wizard, or download the folder) — it's not in version
  control.
- **`staticfiles/`** — rebuilt from `static/` by `collectstatic` on every
  deploy (Part 6 / the ongoing workflow). Committing it would just be merge
  noise for a folder that's entirely derived from other tracked files.
- **`venv/`** — your local dev virtualenv. The server has its own, created
  by Setup Python App (Part 3), with its own path.

`git pull` only ever touches files that are tracked in the repo — so pulling
new code can never clobber production data or secrets.

---

## Troubleshooting

**A task fails in the "Deploy HEAD Commit" output**
Read the specific task's output — it tells you which of install / migrate /
collectstatic / ensure_superuser failed and why. Common causes below.

**500 error visiting the site**
In cPanel, type `File Manager` into the search box, navigate to `ims`, look
for `stderr.log` (select it → **View**) — that's the Passenger error log.
Common causes:
- `.env` missing or has a typo in a variable name — re-check Part 4.
- `DATABASE_URL` password wasn't percent-encoded correctly — re-copy the
  exact line from our chat rather than retyping the raw password.
- Migrations not run yet — go to Git Version Control → Manage → Pull or
  Deploy → **Deploy HEAD Commit** again (safe to re-run any time, every
  task is idempotent).

**"Access denied for user" on the database**
The user isn't linked to the database with privileges — redo Part 1.

**Static files (CSS/images) missing, page looks unstyled**
`collectstatic` didn't run or failed — re-run **Deploy HEAD Commit** and
read that specific task's output for the error.

**Emails not sending**
No Terminal means no quick one-off test command — instead, use the app
itself: once you're logged in as `admin` (Part 4/6), do anything that
triggers an email (e.g. use **Forgot password** on the login page with the
admin account's email) and check the inbox, including spam. If nothing
arrives:
- Double-check `EMAIL_USE_SSL=True` and `EMAIL_USE_TLS=False` together —
  port 465 is implicit SSL, not STARTTLS, and mixing those up is the most
  common cause of a silent hang or a connection error here.
- Re-check `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` for typos in `.env`.
- After fixing `.env`, you must restart the app for the change to take
  effect (see next item) — editing `.env` alone doesn't do that.

**After editing `.env` directly (not through a git pull), the site doesn't
pick up the change**
`.env` isn't tracked by git, so a `git pull`/deploy doesn't know it changed
and won't automatically restart the app for you. Force a restart either by
clicking **Deploy HEAD Commit** again (its last task always touches
`tmp/restart.txt`, regardless of what changed in git), or manually: File
Manager → `ims` → `tmp` folder (create it if missing) → **+ File** →
name it `restart.txt` → **Create New File**. Passenger picks up a fresh
`tmp/restart.txt` on the next request either way.
