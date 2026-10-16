"""Tests for branch comparison and PR creation."""

from pathlib import Path
from worktreeforge.core.git_client import GitClient
from worktreeforge.core.supervisor import WorktreeSupervisor


def test_branch_compare(temp_git_repo: Path, tmp_path: Path):
    supervisor = WorktreeSupervisor(repo_root=temp_git_repo)
    client = GitClient(cwd=temp_git_repo)

    # Create new worktree
    wt_path = tmp_path / "wt_compare"
    supervisor.create_worktree("feature/compare-demo", target_path=wt_path)

    # Add a commit inside the new worktree
    new_file = wt_path / "feature.py"
    new_file.write_text("print('feature code')\n", encoding="utf-8")
    client.run(["add", "feature.py"], cwd=wt_path)
    client.run(["commit", "-m", "feat: add feature code"], cwd=wt_path)

    # Compare
    cmp = supervisor.compare_branch("feature/compare-demo", base_branch="main")
    assert cmp.ahead_count == 1
    assert cmp.behind_count == 0
    assert len(cmp.commits) == 1
    assert "add feature code" in cmp.commits[0]["message"]
    assert any("feature.py" in f["path"] for f in cmp.changed_files)
