#!/bin/sh
set -e

if [ -n "${DATABASE_URL:-}" ]; then
    python -m docker.wait_for_db

    flask --app run.py db upgrade
    flask --app run.py cleanup-token-blocklist
fi

exec "$@"
