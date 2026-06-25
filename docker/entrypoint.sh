#!/usr/bin/env bash
# Container entrypoint: wait for the database, apply migrations, optionally seed a
# superuser, then exec the given command (gunicorn by default, runserver in dev).
set -euo pipefail

echo "[entrypoint] applying database migrations…"
python manage.py migrate --noinput

# Optionally create an admin from env so the app is usable immediately.
# Set DJANGO_SUPERUSER_EMAIL (+ DJANGO_SUPERUSER_PASSWORD) to enable.
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ]; then
  echo "[entrypoint] ensuring superuser ${DJANGO_SUPERUSER_EMAIL} exists…"
  python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
U = get_user_model()
email = os.environ['DJANGO_SUPERUSER_EMAIL']
if not U.objects.filter(email=email).exists():
    U.objects.create_superuser(
        username=os.environ.get('DJANGO_SUPERUSER_USERNAME', email.split('@')[0]),
        email=email,
        password=os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin'),
    )
    print('  created')
else:
    print('  already present')
"
fi

# Collect static only when running the production (gunicorn) command.
if [ "${1:-}" = "gunicorn" ]; then
  echo "[entrypoint] collecting static files…"
  python manage.py collectstatic --noinput >/dev/null 2>&1 || true
fi

echo "[entrypoint] starting: $*"
exec "$@"
