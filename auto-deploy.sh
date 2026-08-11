#!/bin/bash
# Runs on the cPanel server via a scheduled Cron Job so a `git push` on your
# dev machine reaches the live site on its own -- no manual SSH-in-and-pull
# needed. Silent when there's nothing new to deploy (cPanel emails a cron
# job's stdout/stderr, so a quiet tick with no output means no email);
# prints a summary -- which cPanel will then email you -- only when it
# actually deploys something, or when something goes wrong.
#
# ONE-TIME SETUP (cPanel -> Cron Jobs -> Add New Cron Job):
#   Command:  bash /home/roshanda/cleantech/auto-deploy.sh
#   Schedule: every 5-10 minutes is reasonable (Common Settings dropdown,
#             or manually "*/10 * * * *"). Faster doesn't get you much --
#             a `git pull --ff-only` with nothing new is nearly instant.
#
# Troubleshooting: if cron logs "command not found" for git, cPanel's cron
# environment may not have the same PATH as an interactive shell -- run
# `which git` over SSH once and hardcode the absolute path below if needed.
#
# Whole body is wrapped in main() and called as the very last line on
# purpose: this script updates itself via the same `git pull` it runs, and
# calling a function (which bash parses in full before running) rather than
# executing top-level statements as they're read avoids bash getting
# confused if the file on disk changes mid-run.
set -uo pipefail

main() {
  local repo_dir="/home/roshanda/cleantech"
  local log_file="$repo_dir/tmp/auto-deploy.log"
  local lock_file="$repo_dir/tmp/auto-deploy.lock"

  mkdir -p "$repo_dir/tmp"
  exec 9>"$lock_file"
  flock -n 9 || exit 0  # a previous run is still going -- skip this tick, stay quiet

  cd "$repo_dir" || { echo "auto-deploy: repo dir not found: $repo_dir"; exit 1; }

  local before pull_output pull_status after
  before=$(git rev-parse HEAD)
  pull_output=$(git pull --ff-only origin main 2>&1)
  pull_status=$?
  after=$(git rev-parse HEAD)

  if [ "$pull_status" -ne 0 ]; then
    echo "$(date -Iseconds) git pull FAILED:" | tee -a "$log_file"
    echo "$pull_output" | tee -a "$log_file"
    exit 1
  fi

  if [ "$before" = "$after" ]; then
    exit 0  # nothing new -- no output, no email
  fi

  echo "$(date -Iseconds) deploying $before -> $after" | tee -a "$log_file"
  local deploy_output deploy_status
  deploy_output=$(bash deploy.sh 2>&1)
  deploy_status=$?
  echo "$deploy_output" | tee -a "$log_file"

  if [ "$deploy_status" -ne 0 ]; then
    echo "$(date -Iseconds) deploy.sh FAILED (exit $deploy_status)" | tee -a "$log_file"
    exit 1
  fi

  echo "$(date -Iseconds) deploy OK" | tee -a "$log_file"
}

main "$@"
