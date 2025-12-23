from io import StringIO
from unittest.mock import MagicMock, patch

import pytest  # type: ignore[reportMissingImports]
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class TestTriggerTask(TestCase):
    """Test cases for trigger_task management command."""

    def setUp(self):
        """Set up test fixtures."""
        self.stdout = StringIO()
        self.stderr = StringIO()

    @patch("core.management.commands.trigger_task.get_task_map")
    def test_trigger_task_success_sync(self, mock_get_task_map):
        """
        GIVEN a valid task name
        WHEN trigger_task is called without --async flag
        THEN the task should run synchronously and return success
        """
        mock_task = MagicMock()
        mock_task.return_value = {"status": "success", "message": "Task completed"}
        mock_task_map = {
            "scheduled_market_data_ingestion": mock_task,
        }
        mock_get_task_map.return_value = mock_task_map

        call_command(
            "trigger_task",
            "scheduled_market_data_ingestion",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        output = self.stdout.getvalue()
        assert "Triggering task: scheduled_market_data_ingestion" in output
        assert "Running task synchronously" in output
        assert "Task 'scheduled_market_data_ingestion' completed successfully" in output
        mock_task.assert_called_once()

    @patch("core.management.commands.trigger_task.get_task_map")
    def test_trigger_task_success_async(self, mock_get_task_map):
        """
        GIVEN a valid task name
        WHEN trigger_task is called with --async flag
        THEN the task should be queued via Celery
        """
        mock_task = MagicMock()
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_task.delay.return_value = mock_result
        mock_task_map = {
            "scheduled_market_data_ingestion": mock_task,
        }
        mock_get_task_map.return_value = mock_task_map

        call_command(
            "trigger_task",
            "scheduled_market_data_ingestion",
            "--async",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        output = self.stdout.getvalue()
        assert "Triggering task: scheduled_market_data_ingestion" in output
        assert "Task 'scheduled_market_data_ingestion' queued successfully" in output
        assert "Task ID: task-123" in output
        mock_task.delay.assert_called_once()

    def test_trigger_task_invalid_task_name(self):
        """
        GIVEN an invalid task name
        WHEN trigger_task is called
        THEN a CommandError should be raised
        """
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command(
                "trigger_task",
                "invalid_task_name",
                stdout=self.stdout,
                stderr=self.stderr,
            )

    @patch("core.management.commands.trigger_task.get_task_map")
    def test_trigger_task_error(self, mock_get_task_map):
        """
        GIVEN a task that raises an exception
        WHEN trigger_task is called
        THEN a CommandError should be raised
        """
        mock_task = MagicMock()
        mock_task.side_effect = Exception("Task execution error")
        mock_task_map = {
            "scheduled_market_data_ingestion": mock_task,
        }
        mock_get_task_map.return_value = mock_task_map

        with pytest.raises(CommandError) as exc_info:
            call_command(
                "trigger_task",
                "scheduled_market_data_ingestion",
                stdout=self.stdout,
                stderr=self.stderr,
            )

        assert "Error executing task 'scheduled_market_data_ingestion'" in str(
            exc_info.value
        )
        assert "Task execution error" in str(exc_info.value)

    @patch("core.management.commands.trigger_task.get_task_map")
    def test_trigger_task_all_available_tasks(self, mock_get_task_map):
        """
        GIVEN all available tasks in the task map
        WHEN trigger_task help is displayed
        THEN all task names should be listed
        """
        mock_task_map = {
            "scheduled_market_data_ingestion": MagicMock(),
            "scheduled_stir_prices_ingestion": MagicMock(),
            "scheduled_economic_data_and_schedule_update": MagicMock(),
        }
        mock_get_task_map.return_value = mock_task_map

        # Test that each task can be triggered
        for task_name in mock_task_map.keys():
            mock_task = mock_task_map[task_name]
            mock_task.return_value = {"status": "success"}

            call_command(
                "trigger_task",
                task_name,
                stdout=self.stdout,
                stderr=self.stderr,
            )

            assert f"Triggering task: {task_name}" in self.stdout.getvalue()
            mock_task.assert_called_once()
            self.stdout = StringIO()  # Reset for next iteration
