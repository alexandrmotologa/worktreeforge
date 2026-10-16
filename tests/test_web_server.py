"""Tests for FastAPI Web Studio server endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient

from worktreeforge.core.supervisor import WorktreeSupervisor
import worktreeforge.web.server as web_server

client = TestClient(web_server.app)


def test_api_status(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    web_server._supervisor_instance = WorktreeSupervisor(repo_root=temp_git_repo)

    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["repo_name"] == temp_git_repo.name
    assert data["total_worktrees"] == 1


def test_api_worktrees_list(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    web_server._supervisor_instance = WorktreeSupervisor(repo_root=temp_git_repo)

    response = client.get("/api/worktrees")
    assert response.status_code == 200
    worktrees = response.json()
    assert len(worktrees) == 1
    assert worktrees[0]["is_main"] is True


def test_api_ports(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    web_server._supervisor_instance = WorktreeSupervisor(repo_root=temp_git_repo)

    response = client.get("/api/ports?check=true")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_stashes(temp_git_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_git_repo)
    web_server._supervisor_instance = WorktreeSupervisor(repo_root=temp_git_repo)

    response = client.get("/api/stashes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
