"""Tests for StashInspector engine."""

from pathlib import Path
from worktreeforge.core.git_client import GitClient
from worktreeforge.stash.inspector import StashInspector


def test_stash_inspector_search(temp_git_repo: Path):
    client = GitClient(cwd=temp_git_repo)
    inspector = StashInspector(git_client=client, cwd=temp_git_repo)

    # Initially empty
    assert len(inspector.list_all()) == 0

    # Create change and stash
    test_file = temp_git_repo / "auth_handler.py"
    test_file.write_text("def authenticate():\n    return 'secret_token_123'\n", encoding="utf-8")
    client.run(["add", "auth_handler.py"])
    client.run(["stash", "push", "-m", "WIP: auth token implementation"])

    # Search by message
    results = inspector.search("auth token")
    assert len(results) == 1
    assert results[0][0].index == 0

    # Search by content inside diff
    results_diff = inspector.search("secret_token_123")
    assert len(results_diff) == 1

    # Apply and clean up
    inspector.apply(0, drop=True)
    assert len(inspector.list_all()) == 0
