#!/bin/bash
# Run this on the cPanel server (via Terminal or SSH) after every `git pull`.
# Not used locally -- local dev just runs manage.py directly against venv/.
#
# ONE-TIME SETUP: edit the line below to the exact "Enter to the virtual
# environment" command shown on cPanel's Setup Python App page for this app
# (Setup Python App -> your app -> copy the `source .../activate` line).
set -e

source /home/roshanda/virtualenv/ims/3.13/bin/activate

cd "$(dirname "$0")"

pip install -r requirements/prod.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_superuser

mkdir -p tmp
touch tmp/restart.txt

echo "Deployed. Passenger will restart the app on the next request."
