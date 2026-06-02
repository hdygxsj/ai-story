#!/usr/bin/env sh
set -eu

echo "Running database migrations..."
attempt=1
until alembic upgrade head; do
  if [ "$attempt" -ge 30 ]; then
    echo "Database migrations failed after ${attempt} attempts."
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 2
done

exec "$@"
