"""Tests for background ProcessManager dev server supervision."""

from pathlib import Path
import time
from worktreeforge.core.process_manager import ProcessManager


def test_detect_dev_command(tmp_path: Path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text('{"scripts": {"dev": "vite"}}\n', encoding="utf-8")
    cmd = ProcessManager.detect_dev_command(tmp_path)
    assert "npm run dev" in cmd


def test_start_and_stop_process(tmp_path: Path):
    pm = ProcessManager()
    dummy_cmd = 'python -c "import time, sys; sys.stdout.write(\'HELLO_DEV\\n\'); sys.stdout.flush(); time.sleep(2)"'

    info = pm.start_process(
        worktree_path=tmp_path,
        branch="feature/process-test",
        command=dummy_cmd,
    )

    assert info.pid > 0
    assert info.status == "RUNNING"

    # Give process time to emit line
    time.sleep(0.5)

    logs = pm.get_logs(tmp_path)
    assert any("HELLO_DEV" in line for line in logs)

    # Stop process
    stopped = pm.stop_process(tmp_path)
    assert stopped is True

    status_info = pm.get_info(tmp_path)
    assert status_info is not None
    assert "STOPPED" in status_info.status or "EXITED" in status_info.status
