"""Pytest test fixtures for WorktreeForge."""

import os
from pathlib import Path
import subprocess
import tempfile
import pytest

from worktreeforge.core.git_client import GitClient
from worktreeforge.core.supervisor import WorktreeSupervisor


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Create a temporary initialized Git repository with an initial commit."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    # Initial file and commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")

    # Sample .env
    env_file = repo_dir / ".env"
    env_file.write_text("PORT=3000\nAPI_PORT=8000\nSECRET_KEY=test\n", encoding="utf-8")

    # Sample package.json
    pkg_json = repo_dir / "package.json"
    pkg_json.write_text(
        '{"name": "test-app", "scripts": {"dev": "next dev -p 3000"}}\n',
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )

    return repo_dir


@pytest.fixture
def supervisor(temp_git_repo: Path):
    """Create a WorktreeSupervisor instance targeting the test repo."""
    return WorktreeSupervisor(repo_root=temp_git_repo)
