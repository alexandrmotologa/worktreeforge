"""Tests for DependencyLinker directory junctions and symlinks."""

from pathlib import Path
from worktreeforge.core.dependency_linker import DependencyLinker


def test_detect_shareable_dependencies(tmp_path: Path):
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    venv = tmp_path / ".venv"
    venv.mkdir()

    found = DependencyLinker.detect_shareable(tmp_path)
    assert "node_modules" in found
    assert ".venv" in found


def test_link_and_unlink_worktree(tmp_path: Path):
    src_repo = tmp_path / "src_repo"
    src_repo.mkdir()
    (src_repo / "node_modules").mkdir()
    (src_repo / "node_modules" / "test_pkg.txt").write_text("package data", encoding="utf-8")

    dst_wt = tmp_path / "dst_wt"
    dst_wt.mkdir()

    # Link
    linked = DependencyLinker.link_worktree(
        repo_root=src_repo,
        worktree_path=dst_wt,
        targets=["node_modules"],
    )
    assert "node_modules" in linked
    assert (dst_wt / "node_modules").is_dir()
    assert (dst_wt / "node_modules" / "test_pkg.txt").is_file()

    # Unlink
    unlinked = DependencyLinker.unlink_worktree(
        worktree_path=dst_wt,
        targets=["node_modules"],
    )
    assert "node_modules" in unlinked
    assert not (dst_wt / "node_modules").exists()

    # Original data must remain intact!
    assert (src_repo / "node_modules" / "test_pkg.txt").is_file()
