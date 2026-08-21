"""Safety checks shared by local development database commands."""

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection


ALLOWED_ENVIRONMENTS = {"dev", "development", "local"}
ALLOWED_DATABASE_NAMES = {"scicommons_dev"}


def require_local_development_database() -> None:
    """Refuse destructive or synthetic-data operations outside the local DB."""
    environment = str(settings.ENVIRONMENT).lower()
    database_name = str(connection.settings_dict["NAME"])

    if (
        not settings.DEBUG
        or environment not in ALLOWED_ENVIRONMENTS
        or database_name not in ALLOWED_DATABASE_NAMES
    ):
        raise CommandError(
            "Refusing to modify this database. Development data commands require "
            "DEBUG=True, ENVIRONMENT=local/dev/development, and "
            "DB_NAME=scicommons_dev."
        )
