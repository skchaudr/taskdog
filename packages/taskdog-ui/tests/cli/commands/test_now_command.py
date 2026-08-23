"""Tests for the now command."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from taskdog.cli.commands.now import DEFAULT_FIELDS, DEFAULT_LIMIT, now_command
from taskdog_core.application.dto.next_tasks_output import NextTasksOutput
from taskdog_core.application.dto.task_dto import TaskRowDto
from taskdog_core.domain.entities.task import TaskStatus


class TestNowCommand:
    """Test cases for the now command."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.console_writer = MagicMock()
        self.api_client = MagicMock()
        self.cli_context = MagicMock()
        self.cli_context.console_writer = self.console_writer
        self.cli_context.api_client = self.api_client

    def _result_with(self, count: int) -> NextTasksOutput:
        """Build a NextTasksOutput carrying `count` real task rows."""
        now = datetime(2026, 8, 21, 9, 0, 0)
        tasks = [
            TaskRowDto(
                id=index,
                name=f"Task {index}",
                priority=None,
                status=TaskStatus.PENDING,
                planned_start=None,
                planned_end=None,
                deadline=None,
                actual_start=None,
                actual_end=None,
                estimated_duration=None,
                actual_duration_hours=None,
                is_fixed=False,
                depends_on=[],
                tags=[],
                is_archived=False,
                is_finished=False,
                created_at=now,
                updated_at=now,
            )
            for index in range(1, count + 1)
        ]
        return NextTasksOutput(tasks=tasks)

    @patch("taskdog.cli.commands.now.render_table")
    def test_defaults_to_three_tasks(self, mock_render_table):
        """Without options the command asks for the top three executable tasks."""
        self.api_client.get_executable_tasks.return_value = self._result_with(3)

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        self.api_client.get_executable_tasks.assert_called_once_with(
            tags=None, limit=DEFAULT_LIMIT
        )
        mock_render_table.assert_called_once()

    @patch("taskdog.cli.commands.now.render_table")
    def test_renders_focused_field_set_by_default(self, mock_render_table):
        """The default view is narrow so the output stays scannable."""
        self.api_client.get_executable_tasks.return_value = self._result_with(1)

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        assert mock_render_table.call_args[1]["fields"] == DEFAULT_FIELDS

    @patch("taskdog.cli.commands.now.render_table")
    def test_wraps_ranked_tasks_in_list_output(self, mock_render_table):
        """Ranked rows are passed through in order with matching counts."""
        api_result = self._result_with(2)
        self.api_client.get_executable_tasks.return_value = api_result

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        output = mock_render_table.call_args[0][1]
        assert output.tasks == api_result.tasks
        assert output.total_count == 2
        assert output.filtered_count == 2

    @patch("taskdog.cli.commands.now.render_table")
    def test_limit_option(self, mock_render_table):
        """--limit overrides the default cap."""
        self.api_client.get_executable_tasks.return_value = self._result_with(1)

        result = self.runner.invoke(now_command, ["--limit", "7"], obj=self.cli_context)

        assert result.exit_code == 0
        assert self.api_client.get_executable_tasks.call_args[1]["limit"] == 7

    @patch("taskdog.cli.commands.now.render_table")
    def test_rejects_non_positive_limit(self, mock_render_table):
        """A limit below one is a usage error, not an empty table."""
        result = self.runner.invoke(now_command, ["--limit", "0"], obj=self.cli_context)

        assert result.exit_code != 0
        self.api_client.get_executable_tasks.assert_not_called()

    @patch("taskdog.cli.commands.now.render_table")
    def test_tag_filter_uses_or_logic(self, mock_render_table):
        """Repeated --tag values are forwarded as a list."""
        self.api_client.get_executable_tasks.return_value = self._result_with(1)

        result = self.runner.invoke(
            now_command, ["-t", "work", "-t", "urgent"], obj=self.cli_context
        )

        assert result.exit_code == 0
        assert self.api_client.get_executable_tasks.call_args[1]["tags"] == [
            "work",
            "urgent",
        ]

    @patch("taskdog.cli.commands.now.render_table")
    def test_fields_option_overrides_default(self, mock_render_table):
        """--fields replaces the focused default field set."""
        self.api_client.get_executable_tasks.return_value = self._result_with(1)

        result = self.runner.invoke(
            now_command, ["--fields", "id,name"], obj=self.cli_context
        )

        assert result.exit_code == 0
        assert mock_render_table.call_args[1]["fields"] == ["id", "name"]

    @patch("taskdog.cli.commands.now.render_table")
    def test_empty_result_prints_message_without_table(self, mock_render_table):
        """Nothing executable is a sentence, not an empty table."""
        self.api_client.get_executable_tasks.return_value = self._result_with(0)

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        mock_render_table.assert_not_called()
        self.console_writer.info.assert_called_once()

    def _ranked_result(self, ranked: int, unranked: int) -> NextTasksOutput:
        """Build a result where `ranked` rows carry a deadline and the rest do not."""
        now = datetime(2026, 8, 21, 9, 0, 0)
        tasks = [
            TaskRowDto(
                id=index,
                name=f"Task {index}",
                priority=None,
                status=TaskStatus.PENDING,
                planned_start=None,
                planned_end=None,
                deadline=now if index <= ranked else None,
                actual_start=None,
                actual_end=None,
                estimated_duration=None,
                actual_duration_hours=None,
                is_fixed=False,
                depends_on=[],
                tags=[],
                is_archived=False,
                is_finished=False,
                created_at=now,
                updated_at=now,
            )
            for index in range(1, ranked + unranked + 1)
        ]
        return NextTasksOutput(tasks=tasks)

    @patch("taskdog.cli.commands.now.render_table")
    def test_warns_when_no_task_has_a_ranking_field(self, mock_render_table):
        """Rows with no deadline/priority/estimate fall out in id order, not rank."""
        self.api_client.get_executable_tasks.return_value = self._ranked_result(0, 3)

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        self.console_writer.warning.assert_called_once()
        message = self.console_writer.warning.call_args[0][0]
        assert "Not ranked" in message
        assert "capture order" in message
        # The rows are still shown - the warning qualifies them, it does not hide them.
        mock_render_table.assert_called_once()

    @patch("taskdog.cli.commands.now.render_table")
    def test_warns_when_only_some_tasks_are_rankable(self, mock_render_table):
        """A partially populated ledger still ranks, but the gap is worth saying."""
        self.api_client.get_executable_tasks.return_value = self._ranked_result(1, 2)

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        message = self.console_writer.warning.call_args[0][0]
        assert "Partially ranked" in message
        assert "2 of 3" in message
        mock_render_table.assert_called_once()

    @patch("taskdog.cli.commands.now.render_table")
    def test_stays_quiet_when_every_task_is_rankable(self, mock_render_table):
        """No warning when the ordering actually means something."""
        self.api_client.get_executable_tasks.return_value = self._ranked_result(3, 0)

        result = self.runner.invoke(now_command, [], obj=self.cli_context)

        assert result.exit_code == 0
        self.console_writer.warning.assert_not_called()
        mock_render_table.assert_called_once()
