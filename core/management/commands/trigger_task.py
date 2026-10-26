"""
Django management command to manually trigger scheduled Celery tasks.
"""

from django.core.management.base import BaseCommand, CommandError

from central_banks_overview.tasks import (
    scheduled_stir_futures_price_update_logs_cleanup,
    scheduled_stir_prices_ingestion,
    scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings,
)
from economic_overview.tasks import (
    scheduled_economic_data_and_schedule_update,
    scheduled_economic_data_update_logs_cleanup,
)
from market_overview.tasks import (
    scheduled_holidays_ingestion,
    scheduled_market_data_ingestion,
    scheduled_price_update_logs_cleanup,
)

TASK_MAP = {
    "scheduled_market_data_ingestion": scheduled_market_data_ingestion,
    "scheduled_stir_prices_ingestion": scheduled_stir_prices_ingestion,
    "scheduled_economic_data_and_schedule_update": (
        scheduled_economic_data_and_schedule_update
    ),
    "scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings": (
        scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings
    ),
    "scheduled_price_update_logs_cleanup": scheduled_price_update_logs_cleanup,
    "scheduled_stir_futures_price_update_logs_cleanup": (
        scheduled_stir_futures_price_update_logs_cleanup
    ),
    "scheduled_economic_data_update_logs_cleanup": (
        scheduled_economic_data_update_logs_cleanup
    ),
    "scheduled_holidays_ingestion": scheduled_holidays_ingestion,
}


class Command(BaseCommand):
    """Management command to trigger scheduled Celery tasks."""

    help = (
        "Manually trigger a scheduled Celery task. "
        f"Available tasks: {', '.join(TASK_MAP.keys())}"
    )

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "task_name",
            type=str,
            help="Name of the task to trigger",
            choices=list(TASK_MAP.keys()),
        )
        parser.add_argument(
            "--async",
            action="store_true",
            help="Run task asynchronously via Celery (default: run synchronously)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        task_name = options["task_name"]
        run_async = options["async"]

        task_function = TASK_MAP[task_name]

        self.stdout.write(self.style.SUCCESS(f"Triggering task: {task_name}"))

        try:
            if run_async:
                # Run via Celery (asynchronously)
                result = task_function.delay()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Task '{task_name}' queued successfully. "
                        f"Task ID: {result.id}"
                    )
                )
            else:
                # Run synchronously (direct function call)
                self.stdout.write(
                    self.style.WARNING("Running task synchronously (not via Celery)...")
                )
                result = task_function()
                self.stdout.write(
                    self.style.SUCCESS(f"Task '{task_name}' completed successfully.")
                )
                if result:
                    self.stdout.write(f"Result: {result}")

        except Exception as e:
            raise CommandError(f"Error executing task '{task_name}': {str(e)}")
