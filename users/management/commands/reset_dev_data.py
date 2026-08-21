"""Reset the local development database and recreate synthetic records."""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from users.management.dev_database import require_local_development_database


class Command(BaseCommand):
    help = "Flush scicommons_dev and recreate its synthetic development dataset"

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm deletion of all rows in the local development database",
        )

    def handle(self, *args, **options):
        require_local_development_database()
        if not options["yes"]:
            raise CommandError(
                "This deletes every row in scicommons_dev. Re-run with --yes to "
                "confirm."
            )

        call_command("flush", interactive=False, verbosity=options["verbosity"])
        call_command("seed_dev_data", verbosity=options["verbosity"])
        self.stdout.write(
            self.style.SUCCESS("Local development database reset complete.")
        )
