"""Tests for WorktreeSupervisor."""

from pathlib import Path
import pytest

from worktreeforge.core.models import PRState, PRStatus
from worktreeforge.core.supervisor import SupervisorError, WorktreeSupervisor


def test_supervisor_create_and_remove(supervisor: WorktreeSupervisor, tmp_path: Path):
    target_dir = tmp_path / "supervisor_wt"

    wt, allocs = supervisor.create_worktree(
        branch="feature/supervisor-test",
        target_path=target_dir,
    )

    assert wt.branch == "feature/supervisor-test"
    assert target_dir.is_dir()
    assert (target_dir / ".env.local").is_file()

    # Verify ports allocated
    assert len(allocs) > 0
    assert "PORT" in wt.active_ports

    # Listing should show the new worktree
    wts = supervisor.list_worktrees(enrich_ports=True, enrich_pr=False)
    assert len(wts) == 2

    # Prevent deleting main worktree
    with pytest.raises(SupervisorError, match="Cannot remove the primary"):
        supervisor.remove_worktree("main")

    # Lock worktree
    supervisor.lock_worktree("feature/supervisor-test", reason="Benchmark in progress")
    locked_wt = supervisor.find_worktree("feature/supervisor-test")
    assert locked_wt.is_locked is True

    # Attempting remove when locked should fail
    with pytest.raises(SupervisorError, match="Worktree is locked"):
        supervisor.remove_worktree("feature/supervisor-test")

    # Unlock and remove
    supervisor.unlock_worktree("feature/supervisor-test")
    removed_wt, released = supervisor.remove_worktree("feature/supervisor-test")
    assert removed_wt.branch == "feature/supervisor-test"
    assert len(released) > 0

    assert not target_dir.exists()


def test_supervisor_dirty_guard(supervisor: WorktreeSupervisor, tmp_path: Path):
    target_dir = tmp_path / "dirty_wt"

    supervisor.create_worktree(
        branch="feature/dirty-test",
        target_path=target_dir,
    )

    # Make uncommitted file
    dirty_file = target_dir / "uncommitted.txt"
    dirty_file.write_text("WIP", encoding="utf-8")

    # Removal without force should fail
    with pytest.raises(SupervisorError, match="uncommitted changes"):
        supervisor.remove_worktree("feature/dirty-test", force=False)

    # Removal with force=True should succeed
    supervisor.remove_worktree("feature/dirty-test", force=True)
    assert not target_dir.exists()
