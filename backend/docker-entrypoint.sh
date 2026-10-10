#!/bin/sh
set -e

# Apply database migrations before the server starts. Compose gates this on the
# db healthcheck, but retry briefly so the image also works when Postgres comes
# up slowly or is started separately.
attempts=0
until alembic upgrade head; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 10 ]; then
    echo "Database migrations failed after ${attempts} attempts." >&2
    exit 1
  fi
  echo "Database not ready yet (attempt ${attempts}); retrying in 2s..."
  sleep 2
done

exec "$@"
