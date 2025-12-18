"""
Django management command to manually trigger scheduled Celery tasks.
"""

from django.core.management.base import BaseCommand, CommandError


def get_task_map():
    """
    Get the task map with lazy imports.
    This function is called after Django is fully configured.
    """
    # Import all task functions (lazy import after Django setup)
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

    # Map task names to their functions
    return {
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

    def __init__(self, *args, **kwargs):
        """Initialize command with lazy task map."""
        super().__init__(*args, **kwargs)
        self._task_map = None

    @property
    def task_map(self):
        """Get task map with lazy loading."""
        if self._task_map is None:
            self._task_map = get_task_map()
        return self._task_map

    @property
    def help(self):
        """Generate help text with available tasks."""
        return (
            "Manually trigger a scheduled Celery task. "
            f"Available tasks: {', '.join(self.task_map.keys())}"
        )

    def add_arguments(self, parser):
        """Add command arguments."""
        # Get task map to populate choices
        task_map = get_task_map()
        parser.add_argument(
            "task_name",
            type=str,
            help="Name of the task to trigger",
            choices=list(task_map.keys()),
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

        task_map = get_task_map()
        task_function = task_map[task_name]

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
