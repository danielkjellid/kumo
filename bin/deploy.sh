#!/bin/sh
# Converge the box to the checked-in compose file. Runs from cron every few
# minutes and from CI after a push, so it has to be safe to run at any time.
set -eu
cd "$(dirname "$0")/.."
docker compose pull --quiet
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
