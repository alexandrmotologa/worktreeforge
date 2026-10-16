"""Tests for new CLI commands: path, init, start, stop, logs, compare."""

from pathlib import Path
from typer.testing import CliRunner

from worktreeforge.cli.main import app

runner = CliRunner()


def test_cli_path_and_init(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)

    # Test path for main
    res_path = runner.invoke(app, ["path", "main"])
    assert res_path.exit_code == 0
    assert str(temp_git_repo.resolve()).lower() in res_path.stdout.lower()

    # Test init
    res_init = runner.invoke(app, ["init", "pwsh"])
    assert res_init.exit_code == 0
    assert "function wtf" in res_init.stdout
