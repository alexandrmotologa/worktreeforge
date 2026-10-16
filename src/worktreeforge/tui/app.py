"""Interactive Textual terminal dashboard for WorktreeForge."""

from pathlib import Path
from typing import Optional
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TextArea,
)

from worktreeforge.core.models import PRState
from worktreeforge.core.supervisor import WorktreeSupervisor


class NewWorktreeModal(ModalScreen[Optional[str]]):
    """Modal dialog for creating a new worktree."""

    DEFAULT_CSS = """
    NewWorktreeModal {
        align: center middle;
    }
    #modal-container {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #modal-buttons {
        margin-top: 1;
        align: right middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Create New Worktree", classes="modal-title")
            yield Label("Branch name:", classes="field-label")
            yield Input(placeholder="e.g. feature/payments", id="branch-input")
            with Horizontal(id="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Create", variant="primary", id="create-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-btn":
            val = self.query_one("#branch-input", Input).value.strip()
            if val:
                self.dismiss(val)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)


class StashModal(ModalScreen[None]):
    """Modal displaying Stash Studio with diff inspection."""

    DEFAULT_CSS = """
    StashModal {
        align: center middle;
    }
    #stash-container {
        width: 90%;
        height: 85%;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #stash-split {
        height: 1fr;
    }
    #stash-table {
        width: 35%;
        height: 1fr;
    }
    #stash-diff {
        width: 65%;
        height: 1fr;
        margin-left: 1;
    }
    #stash-toolbar {
        margin-top: 1;
        align: right middle;
    }
    """

    def __init__(self, supervisor: WorktreeSupervisor):
        super().__init__()
        self.supervisor = supervisor

    def compose(self) -> ComposeResult:
        with Container(id="stash-container"):
            yield Label("WorktreeForge Stash Studio", classes="modal-title")
            with Horizontal(id="stash-split"):
                yield DataTable(id="stash-table")
                yield TextArea(id="stash-diff", read_only=True, language="diff")
            with Horizontal(id="stash-toolbar"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Pop", variant="warning", id="pop-btn")
                yield Button("Drop", variant="error", id="drop-btn")
                yield Button("Close", variant="default", id="close-btn")

    def on_mount(self) -> None:
        table = self.query_one("#stash-table", DataTable)
        table.cursor_type = "row"
        table.add_column("ID", width=10)
        table.add_column("Branch", width=15)
        table.add_column("Message")

        stashes = self.supervisor.stash_inspector.list_all()
        for s in stashes:
            table.add_row(s.id, s.branch, s.message, key=str(s.index))

        if stashes:
            self.load_diff(stashes[0].index)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            try:
                idx = int(str(event.row_key.value))
                self.load_diff(idx)
            except ValueError:
                pass

    def load_diff(self, index: int) -> None:
        try:
            diff = self.supervisor.stash_inspector.get_diff(index)
            text_area = self.query_one("#stash-diff", TextArea)
            text_area.text = diff.raw_diff or "No diff content."
        except Exception as e:
            text_area = self.query_one("#stash-diff", TextArea)
            text_area.text = f"Error loading diff: {str(e)}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        table = self.query_one("#stash-table", DataTable)
        selected = table.cursor_row
        stashes = self.supervisor.stash_inspector.list_all()
        selected_idx = stashes[selected].index if 0 <= selected < len(stashes) else None

        if event.button.id == "apply-btn" and selected_idx is not None:
            self.supervisor.stash_inspector.apply(selected_idx, drop=False)
            self.dismiss()
        elif event.button.id == "pop-btn" and selected_idx is not None:
            self.supervisor.stash_inspector.apply(selected_idx, drop=True)
            self.dismiss()
        elif event.button.id == "drop-btn" and selected_idx is not None:
            self.supervisor.stash_inspector.drop(selected_idx)
            self.dismiss()
        elif event.button.id == "close-btn":
            self.dismiss()


class WorktreeForgeApp(App):
    """Textual Terminal Dashboard for WorktreeForge."""

    CSS = """
    Screen {
        background: #0f141c;
        color: #e6edf3;
    }
    #repo-header {
        background: #161b22;
        padding: 1 2;
        height: 4;
        border-bottom: solid #30363d;
    }
    #stats-row {
        height: 1;
        color: #8b949e;
    }
    #main-container {
        padding: 1;
        height: 1fr;
    }
    #worktrees-table {
        height: 1fr;
        border: solid #30363d;
    }
    #actions-bar {
        height: 3;
        margin-top: 1;
        align: left middle;
    }
    Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        Binding("n", "new_worktree", "New Worktree"),
        Binding("d", "delete_worktree", "Delete"),
        Binding("l", "toggle_lock", "Lock/Unlock"),
        Binding("s", "open_stash", "Stash Studio"),
        Binding("p", "prune_merged", "Prune Merged"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, supervisor: Optional[WorktreeSupervisor] = None):
        super().__init__()
        self.supervisor = supervisor or WorktreeSupervisor()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="repo-header"):
            yield Label(
                f"WorktreeForge  -  Repository: {self.supervisor.repo_root.name}",
                id="repo-title",
            )
            yield Label(
                "Loading statistics...",
                id="stats-row",
            )
        with Container(id="main-container"):
            yield DataTable(id="worktrees-table")
            with Horizontal(id="actions-bar"):
                yield Button("New Worktree [N]", variant="primary", id="btn-new")
                yield Button("Delete [D]", variant="error", id="btn-del")
                yield Button("Lock/Unlock [L]", variant="default", id="btn-lock")
                yield Button("Stash Studio [S]", variant="default", id="btn-stash")
                yield Button("Prune Merged [P]", variant="warning", id="btn-prune")
                yield Button("Refresh [R]", variant="default", id="btn-refresh")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#worktrees-table", DataTable)
        table.cursor_type = "row"
        table.add_column("Branch", width=24)
        table.add_column("Directory", width=28)
        table.add_column("Status", width=12)
        table.add_column("Ports", width=22)
        table.add_column("GitHub PR", width=16)

        self.action_refresh_data()

    def action_refresh_data(self) -> None:
        table = self.query_one("#worktrees-table", DataTable)
        table.clear()

        worktrees = self.supervisor.list_worktrees(enrich_ports=True, enrich_pr=True)
        stats_label = self.query_one("#stats-row", Label)

        active_ports_count = sum(len(w.active_ports) for w in worktrees)
        stats_label.update(
            f"Active Worktrees: {len(worktrees)}   |   Multiplexed Ports: {active_ports_count}   |   Root: {self.supervisor.repo_root}"
        )

        for wt in worktrees:
            branch_label = f"{wt.branch} (main)" if wt.is_main else wt.branch
            dir_name = Path(wt.path).name

            # Status
            if wt.is_locked:
                status_text = Text("LOCKED", style="bold red")
            elif wt.is_dirty:
                status_text = Text("DIRTY", style="bold yellow")
            else:
                status_text = Text("CLEAN", style="green")

            # Ports
            if wt.active_ports:
                ports_text = Text(
                    ", ".join(f"{k}={v}" for k, v in wt.active_ports.items()),
                    style="yellow",
                )
            else:
                ports_text = Text("none", style="dim")

            # PR
            if wt.pr_status and wt.pr_status.state != PRState.NONE:
                st = wt.pr_status.state
                num = f" #{wt.pr_status.number}" if wt.pr_status.number else ""
                if st == PRState.MERGED:
                    pr_text = Text(f"MERGED{num}", style="bold green")
                elif st == PRState.OPEN:
                    pr_text = Text(f"OPEN{num}", style="bold blue")
                elif st == PRState.CLOSED:
                    pr_text = Text(f"CLOSED{num}", style="bold red")
                else:
                    pr_text = Text(f"{st.value}{num}", style="dim")
            else:
                pr_text = Text("-", style="dim")

            table.add_row(
                branch_label,
                dir_name,
                status_text,
                ports_text,
                pr_text,
                key=wt.path,
            )

    def action_new_worktree(self) -> None:
        def on_modal_result(branch_name: Optional[str]) -> None:
            if branch_name:
                try:
                    self.supervisor.create_worktree(branch=branch_name)
                    self.action_refresh_data()
                except Exception as e:
                    self.notify(f"Creation failed: {str(e)}", severity="error")

        self.push_screen(NewWorktreeModal(), on_modal_result)

    def action_delete_worktree(self) -> None:
        table = self.query_one("#worktrees-table", DataTable)
        worktrees = self.supervisor.list_worktrees(enrich_ports=False, enrich_pr=False)
        selected = table.cursor_row
        if 0 <= selected < len(worktrees):
            wt = worktrees[selected]
            if wt.is_main:
                self.notify("Cannot delete primary worktree", severity="warning")
                return
            try:
                self.supervisor.remove_worktree(wt.path, force=True)
                self.notify(f"Deleted worktree: {wt.branch}", severity="information")
                self.action_refresh_data()
            except Exception as e:
                self.notify(f"Delete failed: {str(e)}", severity="error")

    def action_toggle_lock(self) -> None:
        table = self.query_one("#worktrees-table", DataTable)
        worktrees = self.supervisor.list_worktrees(enrich_ports=False, enrich_pr=False)
        selected = table.cursor_row
        if 0 <= selected < len(worktrees):
            wt = worktrees[selected]
            try:
                if wt.is_locked:
                    self.supervisor.unlock_worktree(wt.path)
                    self.notify(f"Unlocked {wt.branch}")
                else:
                    self.supervisor.lock_worktree(wt.path)
                    self.notify(f"Locked {wt.branch}")
                self.action_refresh_data()
            except Exception as e:
                self.notify(f"Lock action failed: {str(e)}", severity="error")

    def action_open_stash(self) -> None:
        self.push_screen(StashModal(self.supervisor))

    def action_prune_merged(self) -> None:
        results = self.supervisor.prune_merged_worktrees(dry_run=False)
        if results:
            cleaned = sum(1 for _, ok, _ in results if ok)
            self.notify(f"Pruned {cleaned} merged worktree(s)")
            self.action_refresh_data()
        else:
            self.notify("No merged PR worktrees found to prune")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-new":
            self.action_new_worktree()
        elif btn_id == "btn-del":
            self.action_delete_worktree()
        elif btn_id == "btn-lock":
            self.action_toggle_lock()
        elif btn_id == "btn-stash":
            self.action_open_stash()
        elif btn_id == "btn-prune":
            self.action_prune_merged()
        elif btn_id == "btn-refresh":
            self.action_refresh_data()


def run_tui(supervisor: Optional[WorktreeSupervisor] = None) -> None:
    """Entry point to launch the TUI application."""
    app = WorktreeForgeApp(supervisor=supervisor)
    app.run()
