#!/bin/sh
# Converge the box to the checked-in compose file. Runs from cron every few
# minutes and from CI after a push, so it has to be safe to run at any time.
set -eu
# Cron and CI can overlap; the second run waits for the first.
[ "${DEPLOY_LOCKED:-}" ] || exec env DEPLOY_LOCKED=1 flock -w 600 "$0" "$0" "$@"
cd "$(dirname "$0")/.."
docker compose pull --quiet
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
