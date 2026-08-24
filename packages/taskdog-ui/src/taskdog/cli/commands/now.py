"""Now command - show only the handful of tasks that are executable right now."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from taskdog.cli.commands.table_helpers import render_table
from taskdog.cli.error_handler import handle_command_errors
from taskdog.shared.click_types.field_list import FieldList
from taskdog_core.application.dto.task_list_output import TaskListOutput

if TYPE_CHECKING:
    from taskdog.cli.context import CliContext

DEFAULT_LIMIT = 5

# Narrower than `list` on purpose - enough to choose between rows, nothing more.
DEFAULT_FIELDS = ["id", "name", "status", "deadline", "duration"]

# The fields ranking actually reads. If a row has none of them set, its position
# carries no information.
RANKING_FIELDS = ("deadline", "priority", "estimated_duration")


@click.command(
    name="now",
    help="Show what to work on right now (ranked, dependency-resolved).",
)
@click.option(
    "--limit",
    "-n",
    type=click.IntRange(min=1),
    default=DEFAULT_LIMIT,
    show_default=True,
    help="Maximum number of tasks to show.",
)
@click.option(
    "--tag",
    "-t",
    multiple=True,
    type=str,
    help="Filter by tags (can be specified multiple times, uses OR logic)",
)
@click.option(
    "--fields",
    "-f",
    type=FieldList(),
    default=None,
    help="Comma-separated list of fields to display (overrides the focused default set).",
)
@click.pass_context
@handle_command_errors("showing executable tasks")
def now_command(
    ctx: click.Context,
    limit: int,
    tag: tuple[str, ...],
    fields: list[str] | None,
) -> None:
    """Show the next tasks to work on.

    Executable means: PENDING or IN_PROGRESS, not archived, and every
    dependency completed. Ranking is in-progress first, then deadline,
    priority, and estimate - the same order the API and MCP tools use.

    Examples:
        taskdog now                    # Top 5 executable tasks
        taskdog now -n 10              # Top 10
        taskdog now -t work            # Only tasks tagged "work"
        taskdog now --fields id,name   # Just IDs and names
    """
    ctx_obj: CliContext = ctx.obj

    tags = list(tag) if tag else None
    result = ctx_obj.api_client.get_executable_tasks(tags=tags, limit=limit)

    if not result.tasks:
        ctx_obj.console_writer.info("Nothing executable right now.")
        return

    # Ranking sorts by deadline, then priority, then estimate. A task captured
    # through the espanso popup has none of them, so a ledger of popup captures
    # sorts by nothing and falls out in id order - the order they were typed.
    # Rendering that as a ranked answer invites acting on a sequence that means
    # nothing, so say so instead.
    ranked = [
        t
        for t in result.tasks
        if any(getattr(t, f, None) is not None for f in RANKING_FIELDS)
    ]
    if not ranked:
        ctx_obj.console_writer.warning(
            f"Not ranked: none of these {len(result.tasks)} tasks has a deadline, "
            "priority, or estimate, so this is capture order, not a recommendation."
        )
    elif len(ranked) < len(result.tasks):
        ctx_obj.console_writer.warning(
            f"Partially ranked: {len(result.tasks) - len(ranked)} of "
            f"{len(result.tasks)} tasks have no deadline, priority, or estimate."
        )

    # NextTasksOutput carries the same TaskRowDto rows the table renderer wants,
    # minus the list metadata; the counts here describe the ranked slice only.
    output = TaskListOutput(
        tasks=result.tasks,
        total_count=len(result.tasks),
        filtered_count=len(result.tasks),
    )
    render_table(ctx_obj, output, fields=fields or DEFAULT_FIELDS)
