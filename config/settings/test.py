"""Test settings: fast password hashing, sqlite fallback, console email."""
from .base import *  # noqa: F403

DEBUG = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Use sqlite for unit tests unless a DATABASE_URL is explicitly provided for CI Postgres.
import os  # noqa: E402

if not os.environ.get("DATABASE_URL"):
    DATABASES = {  # noqa: F405
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
