"""CLI entrypoint for metiscode."""

from __future__ import annotations

import click

from metiscode.session import SessionDB


def _db() -> SessionDB:
    return SessionDB(project_id="global")


@click.group()
def cli() -> None:
    """MetisCode command line interface."""


@cli.command()
@click.option("--model", default="anthropic:claude-sonnet-4-20250514", show_default=True)
@click.option("--agent", default="build", show_default=True)
@click.option("--session-id", default=None)
@click.argument("prompt")
def run(model: str, agent: str, session_id: str | None, prompt: str) -> None:
    """Run a single prompt."""
    click.echo(f"model={model}")
    click.echo(f"agent={agent}")
    if session_id:
        click.echo(f"session_id={session_id}")
    click.echo(prompt)


@cli.command()
@click.option("--port", default=4096, show_default=True, type=int)
@click.option("--host", default="127.0.0.1", show_default=True)
def serve(port: int, host: str) -> None:
    """Start HTTP server placeholder."""
    click.echo(f"Serving on http://{host}:{port}")


@cli.group()
def session() -> None:
    """Session management commands."""


@session.command("list")
def session_list() -> None:
    """List sessions for current project."""
    db = _db()
    import asyncio

    async def _run() -> list[dict[str, object]]:
        await db.init()
        return await db.list_sessions()

    sessions = asyncio.run(_run())
    if not sessions:
        click.echo("[]")
        return
    for item in sessions:
        click.echo(f"{item['id']}\t{item['title']}")


@session.command("show")
@click.argument("session_id")
def session_show(session_id: str) -> None:
    """Show one session."""
    db = _db()
    import asyncio

    async def _run() -> dict[str, object] | None:
        await db.init()
        return await db.get_session(session_id)

    result = asyncio.run(_run())
    click.echo(str(result))


@session.command("delete")
@click.argument("session_id")
def session_delete(session_id: str) -> None:
    """Delete one session."""
    db = _db()
    import asyncio

    async def _run() -> None:
        await db.init()
        await db.delete_session(session_id)

    asyncio.run(_run())
    click.echo(f"deleted {session_id}")


@cli.command()
def tui() -> None:
    """Launch TUI placeholder."""
    click.echo("TUI is not implemented yet.")

