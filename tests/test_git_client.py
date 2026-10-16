"""Tests for Git native subprocess client."""

from pathlib import Path
import pytest

from worktreeforge.core.git_client import GitClient, GitError


def test_get_repo_root(temp_git_repo: Path):
    client = GitClient(cwd=temp_git_repo)
    root = client.get_repo_root()
    assert root.resolve() == temp_git_repo.resolve()


def test_list_worktrees(temp_git_repo: Path):
    client = GitClient(cwd=temp_git_repo)
    worktrees = client.list_worktrees()
    assert len(worktrees) == 1
    assert worktrees[0].is_main is True
    assert worktrees[0].branch in ("main", "master")
    assert worktrees[0].is_dirty is False


def test_add_and_remove_worktree(temp_git_repo: Path, tmp_path: Path):
    client = GitClient(cwd=temp_git_repo)
    wt_path = tmp_path / "wt_feature"

    # Add worktree
    wt = client.add_worktree(path=wt_path, branch="feature/test-1", new_branch=True)
    assert Path(wt.path).resolve() == wt_path.resolve()
    assert wt.branch == "feature/test-1"

    # Verify list
    worktrees = client.list_worktrees()
    assert len(worktrees) == 2

    # Lock worktree
    client.lock_worktree(wt_path, reason="Testing lock")
    locked_wts = client.list_worktrees()
    locked_wt = next(w for w in locked_wts if Path(w.path).resolve() == wt_path.resolve())
    assert locked_wt.is_locked is True
    assert locked_wt.lock_reason == "Testing lock"

    # Unlock worktree
    client.unlock_worktree(wt_path)
    unlocked_wts = client.list_worktrees()
    unlocked_wt = next(w for w in unlocked_wts if Path(w.path).resolve() == wt_path.resolve())
    assert unlocked_wt.is_locked is False

    # Remove worktree
    client.remove_worktree(wt_path, force=True)
    client.prune_worktrees()

    after_wts = client.list_worktrees()
    assert len(after_wts) == 1


def test_check_dirty(temp_git_repo: Path):
    client = GitClient(cwd=temp_git_repo)
    dirty, files = client.check_dirty(temp_git_repo)
    assert dirty is False

    # Make untracked file
    untracked = temp_git_repo / "untracked.txt"
    untracked.write_text("Hello", encoding="utf-8")

    dirty, files = client.check_dirty(temp_git_repo)
    assert dirty is True
    assert "untracked.txt" in files


def test_stash_operations(temp_git_repo: Path):
    client = GitClient(cwd=temp_git_repo)

    # Make modification
    readme = temp_git_repo / "README.md"
    readme.write_text("# Modified for Stash\n", encoding="utf-8")

    # Stash changes
    client.run(["stash", "push", "-m", "WIP: experimental stash"])

    stashes = client.list_stashes()
    assert len(stashes) == 1
    assert "experimental stash" in stashes[0].message
    assert stashes[0].index == 0

    # Get stash diff
    diff = client.get_stash_diff(0)
    assert "Modified for Stash" in diff.raw_diff
    assert "README.md" in diff.files

    # Drop stash
    client.drop_stash(0)
    after_stashes = client.list_stashes()
    assert len(after_stashes) == 0
