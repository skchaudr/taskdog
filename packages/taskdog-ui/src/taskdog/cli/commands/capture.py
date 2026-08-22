"""Capture command - bulk brain dump of task names, one per line."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click

from taskdog.cli.error_handler import handle_command_errors

if TYPE_CHECKING:
    from taskdog.cli.context import CliContext


@click.command(
    name="capture",
    help="Capture many tasks at once, one name per line (Ctrl-D to finish).",
)
@click.option(
    "--tag",
    "-t",
    multiple=True,
    type=str,
    help="Tags applied to every task in this capture session.",
)
@click.pass_context
@handle_command_errors("capturing tasks")
def capture_command(ctx: click.Context, tag: tuple[str, ...]) -> None:
    """Capture a batch of tasks from stdin, one name per line.

    Deliberately sets no priority, deadline, or estimate: getting the thought
    out of your head is the only job here. Add detail later with `update`.

    Examples:
        taskdog capture                 # Type names, Ctrl-D when done
        taskdog capture -t inbox        # Tag the whole session
        pbpaste | taskdog capture       # Capture a pasted list
        cat ideas.txt | taskdog capture # Capture a file
    """
    ctx_obj: CliContext = ctx.obj
    console_writer = ctx_obj.console_writer
    tags = list(tag) if tag else None

    if sys.stdin.isatty():
        console_writer.info("Enter task names, one per line. Ctrl-D to finish.")

    created = 0
    failed = 0
    for line in sys.stdin:
        name = line.strip()
        if not name:
            continue
        try:
            task = ctx_obj.api_client.create_task(name=name, priority=None, tags=tags)
        # One bad line must not cost the rest of the dump.
        except Exception as exc:
            failed += 1
            console_writer.error(f"capturing '{name}'", exc)
            continue
        created += 1
        console_writer.success(f"#{task.id}  {task.name}")

    if not created and not failed:
        console_writer.info("Nothing captured.")
        return

    console_writer.empty_line()
    summary = f"Captured {created} task(s)."
    if failed:
        summary += f" {failed} failed."
    console_writer.info(summary)
