"""
Django management command to reset PostgreSQL sequences after database imports.

This command is useful when you've imported data from another database and need
to reset the auto-increment sequences to avoid duplicate key violations.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Reset PostgreSQL sequences for all models to avoid duplicate key violations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        with connection.cursor() as cursor:
            # List of models and their corresponding table names
            models_to_reset = [
                ("market_overview_marketpricemodel", "MarketPriceModel"),
                ("market_overview_priceupdatelogmodel", "PriceUpdateLogModel"),
            ]

            for table_name, model_name in models_to_reset:
                try:
                    # Get the current maximum ID from the table
                    cursor.execute(f"SELECT MAX(id) FROM {table_name};")
                    max_id = cursor.fetchone()[0]

                    if max_id is None:
                        self.stdout.write(
                            self.style.WARNING(
                                f"No data found in {model_name}, skipping..."
                            )
                        )
                        continue

                    next_id = max_id + 1

                    if dry_run:
                        self.stdout.write(
                            f"Would reset {model_name} sequence to start from: {next_id}"
                        )
                    else:
                        # Reset the sequence to start from max_id + 1
                        cursor.execute(
                            f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH {next_id};"
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Reset {model_name} sequence to start from: {next_id}"
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error resetting sequence for {model_name}: {str(e)}"
                        )
                    )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        "This was a dry run. Use without --dry-run to actually reset sequences."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("All sequences have been reset successfully!")
                )
