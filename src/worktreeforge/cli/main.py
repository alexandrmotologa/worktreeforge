"""Main Typer CLI entrypoint for WorktreeForge."""

import typer

app = typer.Typer(
    name="worktreeforge",
    help="High-speed Git worktree supervisor, stash studio, and local dev port multiplexer.",
    no_args_is_help=True,
)


@app.callback()
def main_callback():
    """WorktreeForge CLI."""
    pass


if __name__ == "__main__":
    app()
