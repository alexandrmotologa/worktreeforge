"""Tests for Typer CLI commands."""

from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch

from worktreeforge.cli.main import app
from worktreeforge.core.models import WorktreeInfo
from worktreeforge.core.supervisor import WorktreeSupervisor

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "WorktreeForge version" in result.stdout


def test_cli_list(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "main" in result.stdout


def test_cli_ports(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    result = runner.invoke(app, ["ports"])
    assert result.exit_code == 0


def test_cli_stash_list(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    result = runner.invoke(app, ["stash", "list"])
    assert result.exit_code == 0
