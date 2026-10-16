"""Tests for .env.local file generation and patching."""

from pathlib import Path
from worktreeforge.multiplexer.env_patcher import EnvPatcher


def test_create_new_env_local(tmp_path: Path):
    patcher = EnvPatcher()
    ports = {"PORT": 3001, "SERVER_PORT": 8001}

    env_path = patcher.patch_worktree(
        worktree_path=tmp_path,
        branch="feature/payments",
        ports=ports,
    )

    assert env_path.is_file()
    content = env_path.read_text(encoding="utf-8")
    assert "PORT=3001" in content
    assert "SERVER_PORT=8001" in content
    assert "branch: feature/payments" in content


def test_update_existing_env_local(tmp_path: Path):
    target_file = tmp_path / ".env.local"
    target_file.write_text(
        "DATABASE_URL=postgres://localhost/db\nPORT=3000\nCUSTOM_VAR=abc\n",
        encoding="utf-8",
    )

    patcher = EnvPatcher()
    ports = {"PORT": 3002, "NEW_PORT": 9000}

    patcher.patch_worktree(
        worktree_path=tmp_path,
        branch="feature/db",
        ports=ports,
    )

    content = target_file.read_text(encoding="utf-8")
    assert "DATABASE_URL=postgres://localhost/db" in content
    assert "CUSTOM_VAR=abc" in content
    assert "PORT=3002" in content
    assert "NEW_PORT=9000" in content
    # Should not duplicate PORT
    assert content.count("PORT=3002") == 1
    assert "PORT=3000" not in content
