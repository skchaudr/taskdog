"""Tests for the capture command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from taskdog.cli.commands.capture import capture_command


class TestCaptureCommand:
    """Test cases for the capture command."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.console_writer = MagicMock()
        self.api_client = MagicMock()
        self.cli_context = MagicMock()
        self.cli_context.console_writer = self.console_writer
        self.cli_context.api_client = self.api_client
        self.next_id = iter(range(100, 200))
        self.api_client.create_task.side_effect = lambda **kwargs: MagicMock(
            id=next(self.next_id), name=kwargs["name"]
        )

    def test_creates_one_task_per_line(self):
        """Each non-empty stdin line becomes a task."""
        result = self.runner.invoke(
            capture_command, [], obj=self.cli_context, input="first\nsecond\nthird\n"
        )

        assert result.exit_code == 0
        names = [c[1]["name"] for c in self.api_client.create_task.call_args_list]
        assert names == ["first", "second", "third"]

    def test_capture_sets_no_priority(self):
        """Capture must not invent a priority - that is the whole point."""
        result = self.runner.invoke(
            capture_command, [], obj=self.cli_context, input="a task\n"
        )

        assert result.exit_code == 0
        assert self.api_client.create_task.call_args[1]["priority"] is None

    def test_skips_blank_and_whitespace_lines(self):
        """Blank lines are separators, not tasks."""
        result = self.runner.invoke(
            capture_command, [], obj=self.cli_context, input="one\n\n   \ntwo\n"
        )

        assert result.exit_code == 0
        names = [c[1]["name"] for c in self.api_client.create_task.call_args_list]
        assert names == ["one", "two"]

    def test_strips_surrounding_whitespace(self):
        """Leading/trailing spaces are noise from pasting."""
        result = self.runner.invoke(
            capture_command, [], obj=self.cli_context, input="  padded task  \n"
        )

        assert result.exit_code == 0
        assert self.api_client.create_task.call_args[1]["name"] == "padded task"

    def test_empty_input_creates_nothing(self):
        """No input is not an error."""
        result = self.runner.invoke(capture_command, [], obj=self.cli_context, input="")

        assert result.exit_code == 0
        self.api_client.create_task.assert_not_called()
        self.console_writer.info.assert_called()

    def test_one_failure_does_not_abort_the_dump(self):
        """A brain dump must not lose the lines after a failing one."""
        self.api_client.create_task.side_effect = [
            MagicMock(id=1, name="ok one"),
            RuntimeError("boom"),
            MagicMock(id=3, name="ok two"),
        ]

        result = self.runner.invoke(
            capture_command,
            [],
            obj=self.cli_context,
            input="ok one\nbad one\nok two\n",
        )

        assert result.exit_code == 0
        assert self.api_client.create_task.call_count == 3
        self.console_writer.error.assert_called_once()

    def test_tags_are_applied_to_every_captured_task(self):
        """--tag applies to the whole dump, so a session can be labeled once."""
        result = self.runner.invoke(
            capture_command,
            ["-t", "inbox", "-t", "work"],
            obj=self.cli_context,
            input="one\ntwo\n",
        )

        assert result.exit_code == 0
        for call in self.api_client.create_task.call_args_list:
            assert call[1]["tags"] == ["inbox", "work"]

    def test_no_tags_passes_none(self):
        """Without --tag the client receives None, not an empty list."""
        result = self.runner.invoke(
            capture_command, [], obj=self.cli_context, input="one\n"
        )

        assert result.exit_code == 0
        assert self.api_client.create_task.call_args[1]["tags"] is None

    @patch("taskdog.cli.commands.capture.sys.stdin.isatty", return_value=False)
    def test_piped_input_skips_the_prompt(self, mock_isatty):
        """Piped input should not print interactive instructions."""
        result = self.runner.invoke(
            capture_command, [], obj=self.cli_context, input="one\n"
        )

        assert result.exit_code == 0
        printed = " ".join(str(c) for c in self.console_writer.info.call_args_list)
        assert "Ctrl-D" not in printed
