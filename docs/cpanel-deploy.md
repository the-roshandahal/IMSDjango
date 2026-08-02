# Deploying to cPanel

One-time setup, then a two-click update flow for every change after that.

## What you need on the cPanel account

- **Git Version Control** (cPanel feature, used to clone/pull this repo)
- **Setup Python App** (cPanel/CloudLinux feature, runs the app under Passenger)
- **MySQL Databases** (cPanel feature, for the production database)

If any of those aren't in your cPanel dashboard, ask your host to enable them
(all three are standard on CloudLinux-based shared hosting).

## One-time setup

Do these in order -- the Python App step needs the repo files to already be
there, and Git Version Control needs the target folder to be empty.

### 1. Create the MySQL database

cPanel → **MySQL Databases**:
- Create a database, e.g. `cpanelusername_ims`
- Create a user with a strong password, add it to the database with **All Privileges**
- Note the full database name and username -- cPanel prefixes both with your
  cPanel username (`cpanelusername_ims`, `cpanelusername_dbuser`)

### 2. Clone the repo

cPanel → **Git Version Control** → **Create**:
- Clone URL: `https://github.com/the-roshandahal/IMSDjango.git`
- Repository Path: pick an empty directory outside `public_html`, e.g.
  `/home/cpanelusername/ims` (Passenger apps don't need to live under
  `public_html` -- Apache proxies to them by domain/subdomain instead)
- Branch: `main`

### 3. Point a Python App at that same directory

cPanel → **Setup Python App** → **Create Application**:
- Python version: 3.11 or whatever's newest available
- Application root: the **exact same path** you cloned into, e.g. `/home/cpanelusername/ims`
- Application URL: the domain or subdomain this should serve
- Application startup file: `passenger_wsgi.py` (already in the repo)
- Application Entry point: `application`

Creating the app installs a dedicated virtualenv and shows an "Enter to the
virtual environment" command near the top of the page, something like:

```
source /home/cpanelusername/virtualenv/ims/3.11/bin/activate
```

Copy that exact line -- you need it for the next step and it's also what goes
into `deploy.sh` and `.cpanel.yml`.

### 4. Fill in the deploy scripts with your real path

Edit two files (either locally then push, or directly on the server) and
replace the placeholder venv line with the real one from step 3:

- `deploy.sh` (line with `source /home/USERNAME/virtualenv/...`)
- `.cpanel.yml` (line with `export VENV=/home/USERNAME/virtualenv/...`)

### 5. Create `.env` on the server

This file is gitignored on purpose -- it never comes from git, you create it
by hand once, directly in the app directory (`/home/cpanelusername/ims/.env`),
via cPanel's File Manager or Terminal:

```
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<generate one, see below>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=cleantech1.com.au,www.cleantech1.com.au
DATABASE_URL=mysql://cpanelusername_dbuser:dbpassword@localhost:3306/cpanelusername_ims
```

Generate a real secret key (don't reuse the one from your local `.env`):

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`.env.example` in the repo has the same template with comments, for reference.

### 6. First deploy

Via cPanel Terminal (or SSH if you have it):

```
cd /home/cpanelusername/ims
bash deploy.sh
```

This installs dependencies, runs migrations, and collects static files. Then
create your first admin user:

```
source /home/cpanelusername/virtualenv/ims/3.11/bin/activate
python manage.py createsuperuser
```

Visit the app's URL -- it should be live.

## Every update after that

1. Push to `main` on GitHub from your dev machine, as usual.
2. cPanel → **Git Version Control** → this repo → **Manage** → **Pull or Deploy**
   tab → **Update from Remote** (this is `git pull`).
3. Click **Deploy HEAD Commit**. This runs `.cpanel.yml`, which installs any
   new dependencies, runs any new migrations, re-collects static files, and
   restarts the app -- automatically, no Terminal needed.

If you'd rather do it by hand (or `.cpanel.yml` isn't picking up), Terminal
works too:

```
cd /home/cpanelusername/ims
git pull
bash deploy.sh
```

Either path runs the same four things every time: install deps, migrate,
collectstatic, restart. That's what makes pulling safe -- a migration that
only exists in a new commit gets applied automatically before Passenger
starts serving that commit's code.

## Do you need a separate `.gitignore` on cPanel?

No. `.gitignore` is itself a tracked file -- it comes along with every clone
and pull automatically, so the server always has the same one you committed.
You never create or edit a second copy on the server.

What that `.gitignore` deliberately excludes from git -- `.env`, `media/`,
`staticfiles/`, `db.sqlite3` (if you ever use it), `venv/` -- are exactly the
files that must be able to differ between your laptop and the server, or that
get regenerated on the server itself:

- **`.env`** -- real secrets and the production database URL live only on
  the server (step 5 above). A `git pull` never touches a file that was
  never tracked in the first place, so your production `.env` is safe
  forever, no matter how many times you pull.
- **`media/`** -- uploaded photos (hazard reports, employee photos, etc.)
  exist only on the server's disk. Same reasoning: git doesn't know about
  them, so it can't delete or overwrite them on pull. Back this directory up
  yourself (cPanel's Backup Wizard, or just download it periodically) --
  it's not in version control.
- **`staticfiles/`** -- rebuilt from `static/` by `collectstatic` on every
  deploy. Committing it would just create merge noise for a directory that's
  entirely derived.
- **`venv/`** -- your local dev virtualenv. The server has its own,
  created by Setup Python App, activated by the path from step 3.

In short: `git pull` only ever touches files that are tracked in the repo.
Everything cPanel-specific and server-local was deliberately kept out of git,
so pulling new code can never clobber production data or secrets.
