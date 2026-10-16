"""Rich CLI interface for WorktreeForge."""

from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import typer

from worktreeforge import __version__
from worktreeforge.core.git_client import GitError
from worktreeforge.core.models import PRState
from worktreeforge.core.supervisor import SupervisorError, WorktreeSupervisor
from worktreeforge.multiplexer.port_allocator import is_port_available

app = typer.Typer(
    name="worktreeforge",
    help="High-speed Git worktree supervisor, stash studio, and local dev port multiplexer.",
    no_args_is_help=True,
)
stash_app = typer.Typer(
    name="stash",
    help="Inspect, search, and manage Git stashes.",
    no_args_is_help=True,
)
app.add_typer(stash_app, name="stash")

console = Console()


def get_supervisor() -> WorktreeSupervisor:
    """Initialize WorktreeSupervisor for current working directory."""
    try:
        return WorktreeSupervisor()
    except GitError as e:
        console.print(f"[bold red]Git Error:[/] {str(e)}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]WorktreeForge[/] version [bold green]{__version__}[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show version and exit.", callback=version_callback, is_eager=True
    ),
):
    """WorktreeForge command-line supervisor."""
    pass


# -----------------------------------------------------------------------------
# Worktree Commands
# -----------------------------------------------------------------------------


@app.command("list")
def list_worktrees(
    all_details: bool = typer.Option(
        False, "--all", "-a", help="Show additional commit and file details."
    )
):
    """List all active Git worktrees with allocated ports and PR state."""
    supervisor = get_supervisor()
    worktrees = supervisor.list_worktrees(enrich_ports=True, enrich_pr=True)

    if not worktrees:
        console.print("[dim]No worktrees found.[/]")
        return

    table = Table(
        title=f"WorktreeForge: {supervisor.repo_root.name}",
        title_style="bold magenta",
        header_style="bold cyan",
        border_style="dim",
    )

    table.add_column("Branch", style="bold")
    table.add_column("Directory", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Ports", style="yellow")
    table.add_column("GitHub PR", justify="center")

    for wt in worktrees:
        # Branch format
        branch_str = wt.branch
        if wt.is_main:
            branch_str = f"[cyan]{wt.branch}[/] [dim](main)[/]"

        # Directory format
        dir_name = Path(wt.path).name
        dir_str = f"[dim]{dir_name}[/]"

        # Status
        status_parts = []
        if wt.is_locked:
            reason = f": {wt.lock_reason}" if wt.lock_reason else ""
            status_parts.append(f"[bold red]LOCKED{reason}[/]")
        elif wt.is_dirty:
            status_parts.append("[bold yellow]DIRTY[/]")
        else:
            status_parts.append("[green]CLEAN[/]")

        status_str = " ".join(status_parts)

        # Ports
        if wt.active_ports:
            port_items = [f"{k}={v}" for k, v in wt.active_ports.items()]
            ports_str = ", ".join(port_items)
        else:
            ports_str = "[dim]none[/]"

        # GitHub PR
        if wt.pr_status and wt.pr_status.state != PRState.NONE:
            state = wt.pr_status.state
            num = f"#{wt.pr_status.number}" if wt.pr_status.number else ""
            if state == PRState.MERGED:
                pr_str = f"[bold green]MERGED {num}[/]"
            elif state == PRState.OPEN:
                pr_str = f"[bold blue]OPEN {num}[/]"
            elif state == PRState.CLOSED:
                pr_str = f"[bold red]CLOSED {num}[/]"
            else:
                pr_str = f"[dim]{state.value} {num}[/]"
        else:
            pr_str = "[dim]-[/]"

        table.add_row(branch_str, dir_str, status_str, ports_str, pr_str)

    console.print(table)


@app.command("new")
def new_worktree(
    branch: str = typer.Argument(..., help="Branch name for new worktree."),
    base: Optional[str] = typer.Option(
        None, "--base", "-b", help="Base commit, tag, or branch to fork from."
    ),
    path: Optional[str] = typer.Option(
        None, "--path", "-p", help="Custom destination directory."
    ),
    port_offset: Optional[int] = typer.Option(
        None, "--port-offset", help="Explicit port increment offset."
    ),
    no_ports: bool = typer.Option(
        False, "--no-ports", help="Do not allocate ports or update .env.local."
    ),
    open_editor: bool = typer.Option(
        False, "--open", "-o", help="Open newly created worktree in editor."
    ),
):
    """Provision a new Git worktree with automatic non-conflicting port multiplexing."""
    supervisor = get_supervisor()
    target_path = Path(path).resolve() if path else None

    with console.status(f"[bold cyan]Provisioning worktree for '{branch}'...[/]"):
        try:
            wt_info, allocations = supervisor.create_worktree(
                branch=branch,
                base_ref=base,
                target_path=target_path,
                port_offset=port_offset,
                configure_ports=not no_ports,
            )
        except (SupervisorError, GitError) as e:
            console.print(f"[bold red]Error:[/] {str(e)}")
            raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold green]Successfully created worktree![/]\n"
            f"[bold]Branch:[/] {wt_info.branch}\n"
            f"[bold]Location:[/] [cyan]{wt_info.path}[/]\n"
            f"[bold]Ports:[/] "
            + (
                ", ".join(f"{a.port_variable}={a.allocated_port}" for a in allocations)
                if allocations
                else "[dim]none configured[/]"
            ),
            title="WorktreeForge Provisioner",
            border_style="green",
        )
    )

    if open_editor:
        launched = supervisor.open_editor(Path(wt_info.path))
        if launched:
            console.print("[dim]Opened in editor.[/]")
        else:
            console.print("[yellow]No supported editor detected in PATH.[/]")


@app.command("remove")
def remove_worktree(
    identifier: str = typer.Argument(
        ..., help="Branch name, folder name, or path of worktree to remove."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force removal even if uncommitted changes exist."
    ),
    delete_branch: bool = typer.Option(
        False, "--delete-branch", "-d", help="Also delete the local Git branch."
    ),
):
    """Safely remove a worktree directory and release allocated ports."""
    supervisor = get_supervisor()
    try:
        wt, released = supervisor.remove_worktree(
            identifier=identifier, force=force, delete_branch=delete_branch
        )
        ports_str = (
            f" (released ports: {', '.join(str(p.allocated_port) for p in released)})"
            if released
            else ""
        )
        console.print(
            f"[bold green]Removed worktree:[/] [cyan]{wt.branch}[/] at {wt.path}{ports_str}"
        )
    except (SupervisorError, GitError) as e:
        console.print(f"[bold red]Removal failed:[/] {str(e)}")
        raise typer.Exit(code=1)


@app.command("lock")
def lock_worktree(
    identifier: str = typer.Argument(..., help="Worktree branch or path to lock."),
    reason: Optional[str] = typer.Option(
        None, "--reason", "-r", help="Reason for locking the worktree."
    ),
):
    """Lock a worktree to prevent accidental deletion or pruning."""
    supervisor = get_supervisor()
    try:
        wt = supervisor.lock_worktree(identifier, reason=reason)
        msg = f" (Reason: {reason})" if reason else ""
        console.print(f"[bold green]Locked worktree:[/] [cyan]{wt.branch}[/]{msg}")
    except (SupervisorError, GitError) as e:
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)


@app.command("unlock")
def unlock_worktree(
    identifier: str = typer.Argument(..., help="Worktree branch or path to unlock."),
):
    """Unlock a locked worktree."""
    supervisor = get_supervisor()
    try:
        wt = supervisor.unlock_worktree(identifier)
        console.print(f"[bold green]Unlocked worktree:[/] [cyan]{wt.branch}[/]")
    except (SupervisorError, GitError) as e:
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)


@app.command("ports")
def view_ports(
    check: bool = typer.Option(
        True, "--check/--no-check", help="Probe socket availability on localhost."
    ),
):
    """Display active port reservations and check TCP listening status."""
    supervisor = get_supervisor()
    allocations = supervisor.port_allocator.list_all_allocations()

    if not allocations:
        console.print("[dim]No active port allocations recorded in registry.[/]")
        return

    table = Table(
        title="WorktreeForge Port Allocations",
        title_style="bold magenta",
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Branch", style="bold")
    table.add_column("Variable", style="cyan")
    table.add_column("Base Port", justify="right")
    table.add_column("Allocated Port", justify="right", style="bold yellow")
    table.add_column("Socket State", justify="center")

    for alloc in allocations:
        if check:
            free = is_port_available(alloc.allocated_port)
            state_str = "[green]AVAILABLE[/]" if free else "[bold red]LISTENING[/]"
        else:
            state_str = "[dim]UNCHECKED[/]"

        table.add_row(
            alloc.branch,
            alloc.port_variable,
            str(alloc.base_port),
            str(alloc.allocated_port),
            state_str,
        )

    console.print(table)


@app.command("prune")
def prune_worktrees(
    merged: bool = typer.Option(
        False, "--merged", "-m", help="Automatically remove worktrees with merged PRs."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Display what would be deleted without executing."
    ),
):
    """Clean up orphaned worktree metadata and optionally merged PR worktrees."""
    supervisor = get_supervisor()

    if merged:
        with console.status("[bold cyan]Scanning worktrees for merged PRs...[/]"):
            results = supervisor.prune_merged_worktrees(dry_run=dry_run)

        if not results:
            console.print("[dim]No merged PR worktrees found for cleanup.[/]")
            return

        table = Table(
            title="Merged PR Pruning Results",
            title_style="bold magenta",
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Branch", style="bold")
        table.add_column("Directory", style="dim")
        table.add_column("Action Taken", justify="center")

        for wt, success, note in results:
            action_style = "green" if success else "yellow"
            table.add_row(
                wt.branch,
                Path(wt.path).name,
                f"[{action_style}]{note}[/]",
            )

        console.print(table)
    else:
        # Standard git worktree prune
        supervisor.git.prune_worktrees(cwd=supervisor.repo_root)
        console.print("[bold green]Pruned stale Git worktree metadata.[/]")


# -----------------------------------------------------------------------------
# Stash Commands
# -----------------------------------------------------------------------------


@stash_app.command("list")
def list_stashes():
    """Display all Git stashes with author, branch, and touched files."""
    supervisor = get_supervisor()
    stashes = supervisor.stash_inspector.list_all()

    if not stashes:
        console.print("[dim]No Git stashes found in repository.[/]")
        return

    table = Table(
        title="WorktreeForge Stash Studio",
        title_style="bold magenta",
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("ID", style="bold cyan")
    table.add_column("Branch", style="yellow")
    table.add_column("Files", justify="right")
    table.add_column("Changes", justify="right")
    table.add_column("Message", style="white")

    for s in stashes:
        ins = sum(f.insertions for f in s.files)
        dels = sum(f.deletions for f in s.files)
        changes_str = f"[green]+{ins}[/] [red]-{dels}[/]" if s.files else "[dim]0[/]"

        table.add_row(
            s.id,
            s.branch,
            str(len(s.files)),
            changes_str,
            s.message[:60],
        )

    console.print(table)


@stash_app.command("show")
def show_stash(
    index: int = typer.Argument(0, help="Stash index (e.g. 0 for stash@{0})."),
):
    """Display unified diff and touched files for a stash entry."""
    supervisor = get_supervisor()
    try:
        diff = supervisor.stash_inspector.get_diff(index)
    except GitError as e:
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)

    if not diff.raw_diff.strip():
        console.print(f"[dim]Stash index {index} has no diff content.[/]")
        return

    console.print(f"[bold cyan]Diff for {diff.stash_id}:[/]")
    for file_path, file_diff in diff.files.items():
        console.print(f"\n[bold yellow]--- {file_path} ---[/]")
        syntax = Syntax(file_diff, "diff", theme="monokai", line_numbers=True)
        console.print(syntax)


@stash_app.command("search")
def search_stashes(
    query: str = typer.Argument(..., help="Query keyword to search across stashes."),
):
    """Search stashes across messages, file names, authors, and diff contents."""
    supervisor = get_supervisor()
    results = supervisor.stash_inspector.search(query)

    if not results:
        console.print(f"[dim]No stashes matched query '{query}'.[/]")
        return

    console.print(f"[bold green]Found {len(results)} matching stash(es):[/]\n")
    for stash, matches in results:
        console.print(f"[bold cyan]{stash.id}[/] ([yellow]{stash.branch}[/]) - {stash.message}")
        for match in matches[:3]:
            console.print(f"  [dim]->[/] {match}")
        console.print()


@stash_app.command("apply")
def apply_stash(
    index: int = typer.Argument(0, help="Stash index to apply."),
):
    """Apply a stash to current worktree without dropping it."""
    supervisor = get_supervisor()
    try:
        supervisor.stash_inspector.apply(index, drop=False)
        console.print(f"[bold green]Applied stash@{{{index}}} successfully.[/]")
    except GitError as e:
        console.print(f"[bold red]Failed to apply stash:[/] {str(e)}")
        raise typer.Exit(code=1)


@stash_app.command("pop")
def pop_stash(
    index: int = typer.Argument(0, help="Stash index to apply and drop."),
):
    """Apply and drop a stash from the stack."""
    supervisor = get_supervisor()
    try:
        supervisor.stash_inspector.apply(index, drop=True)
        console.print(f"[bold green]Popped stash@{{{index}}} successfully.[/]")
    except GitError as e:
        console.print(f"[bold red]Failed to pop stash:[/] {str(e)}")
        raise typer.Exit(code=1)


@stash_app.command("drop")
def drop_stash(
    index: int = typer.Argument(0, help="Stash index to drop permanently."),
):
    """Drop a stash entry."""
    supervisor = get_supervisor()
    try:
        supervisor.stash_inspector.drop(index)
        console.print(f"[bold green]Dropped stash@{{{index}}} successfully.[/]")
    except GitError as e:
        console.print(f"[bold red]Failed to drop stash:[/] {str(e)}")
        raise typer.Exit(code=1)


# -----------------------------------------------------------------------------
# Dashboard Launchers
# -----------------------------------------------------------------------------


@app.command("tui")
def run_tui_command():
    """Launch interactive Textual terminal user interface."""
    from worktreeforge.tui.app import run_tui
    run_tui()


@app.command("web")
def run_web_command(
    port: int = typer.Option(8990, "--port", "-p", help="Web server port."),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Web server bind host."),
):
    """Launch FastAPI Web Studio dashboard and REST API."""
    import uvicorn
    console.print(f"[bold cyan]Launching WorktreeForge Web Studio at[/] [bold green]http://{host}:{port}[/]")
    uvicorn.run("worktreeforge.web.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
