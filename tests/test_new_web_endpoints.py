"""Tests for new FastAPI REST endpoints: compare, process, browser."""

from pathlib import Path
from fastapi.testclient import TestClient

from worktreeforge.core.supervisor import WorktreeSupervisor
import worktreeforge.web.server as web_server

client = TestClient(web_server.app)


def test_api_process_and_compare(temp_git_repo: Path, monkeypatch, tmp_path: Path):
    monkeypatch.chdir(temp_git_repo)
    sup = WorktreeSupervisor(repo_root=temp_git_repo)
    web_server._supervisor_instance = sup

    # Create worktree
    wt_path = tmp_path / "wt_web_test"
    sup.create_worktree("feature/web-ext", target_path=wt_path)

    # Compare endpoint
    cmp_res = client.get(f"/api/compare?identifier={str(wt_path)}&base=main")
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.json()
    assert cmp_data["target_branch"] == "feature/web-ext"

    # Start dummy process
    dummy_cmd = 'python -c "import time; time.sleep(1)"'
    start_res = client.post(
        "/api/worktrees/process/start",
        json={"identifier": str(wt_path), "command": dummy_cmd},
    )
    assert start_res.status_code == 200
    info = start_res.json()
    assert info["pid"] > 0

    # Logs endpoint
    logs_res = client.get(f"/api/worktrees/process/logs?identifier={str(wt_path)}")
    assert logs_res.status_code == 200

    # Stop process
    stop_res = client.post(
        "/api/worktrees/process/stop",
        json={"identifier": str(wt_path)},
    )
    assert stop_res.status_code == 200
