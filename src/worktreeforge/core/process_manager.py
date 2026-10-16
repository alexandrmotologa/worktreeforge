"""Process manager for supervising development servers inside worktrees."""

from collections import deque
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Deque, Dict, List, Optional

from worktreeforge.core.models import ProcessInfo


class ProcessManager:
    """Manages long-running background processes and log buffers for worktrees."""

    _instance: Optional["ProcessManager"] = None

    def __init__(self, max_log_lines: int = 1000):
        self.max_log_lines = max_log_lines
        self._processes: Dict[str, subprocess.Popen] = {}
        self._process_info: Dict[str, ProcessInfo] = {}
        self._logs: Dict[str, Deque[str]] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ProcessManager":
        """Singleton accessor to preserve running processes across requests."""
        if cls._instance is None:
            cls._instance = ProcessManager()
        return cls._instance

    @staticmethod
    def detect_dev_command(worktree_path: Path) -> str:
        """Detect standard dev server launch command from repository files."""
        # 1. package.json check
        pkg_json = worktree_path / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                scripts = data.get("scripts", {})
                if "dev" in scripts:
                    # Detect package manager
                    if (worktree_path / "pnpm-lock.yaml").is_file():
                        return "pnpm dev"
                    if (worktree_path / "yarn.lock").is_file():
                        return "yarn dev"
                    if (worktree_path / "bun.lockb").is_file() or (worktree_path / "bun.lock").is_file():
                        return "bun dev"
                    return "npm run dev"
                if "start" in scripts:
                    return "npm start"
            except Exception:
                pass

        # 2. Python entrypoints
        if (worktree_path / "main.py").is_file():
            return "python main.py"
        if (worktree_path / "app.py").is_file():
            return "python app.py"

        return ""

    def start_process(
        self,
        worktree_path: Path,
        branch: str,
        command: Optional[str] = None,
    ) -> ProcessInfo:
        """Start a dev server in background and stream logs to ring buffer."""
        norm_key = str(worktree_path.resolve())

        with self._lock:
            # Check if already running
            if norm_key in self._processes:
                proc = self._processes[norm_key]
                if proc.poll() is None:
                    return self._process_info[norm_key]

            cmd_to_run = (command or self.detect_dev_command(worktree_path)).strip()
            if not cmd_to_run:
                raise ValueError(
                    f"No dev command specified or detected in '{worktree_path.name}'"
                )

            # Inherit environment
            env = os.environ.copy()

            # Spawn process with pipes
            proc = subprocess.Popen(
                cmd_to_run,
                cwd=str(worktree_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1,
            )

            started_time = time.strftime("%Y-%m-%d %H:%M:%S")
            info = ProcessInfo(
                worktree_path=norm_key,
                branch=branch,
                command=cmd_to_run,
                pid=proc.pid,
                status="RUNNING",
                started_at=started_time,
            )

            self._processes[norm_key] = proc
            self._process_info[norm_key] = info
            if norm_key not in self._logs:
                self._logs[norm_key] = deque(maxlen=self.max_log_lines)

            # Start background reader thread for stdout
            thread = threading.Thread(
                target=self._log_reader_loop,
                args=(norm_key, proc),
                daemon=True,
            )
            thread.start()

            return info

    def _log_reader_loop(self, key: str, proc: subprocess.Popen) -> None:
        """Background thread streaming output into memory deque."""
        if proc.stdout:
            try:
                for line in iter(proc.stdout.readline, ""):
                    if not line:
                        break
                    with self._lock:
                        if key in self._logs:
                            self._logs[key].append(line.rstrip("\r\n"))
            except Exception:
                pass
            finally:
                proc.stdout.close()

        proc.wait()
        with self._lock:
            if key in self._process_info:
                self._process_info[key].status = "STOPPED" if proc.returncode == 0 else f"EXITED ({proc.returncode})"

    def stop_process(self, worktree_path: Path) -> bool:
        """Terminate process tree cleanly."""
        norm_key = str(worktree_path.resolve())
        with self._lock:
            proc = self._processes.get(norm_key)
            if not proc or proc.poll() is not None:
                if norm_key in self._process_info:
                    self._process_info[norm_key].status = "STOPPED"
                return False

            if sys.platform == "win32":
                # Kill process tree on Windows
                subprocess.run(
                    f"taskkill /F /T /PID {proc.pid}",
                    shell=True,
                    capture_output=True,
                )
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

            if norm_key in self._process_info:
                self._process_info[norm_key].status = "STOPPED"

            return True

    def get_info(self, worktree_path: Path) -> Optional[ProcessInfo]:
        """Fetch running process status for a worktree."""
        norm_key = str(worktree_path.resolve())
        with self._lock:
            info = self._process_info.get(norm_key)
            if info and norm_key in self._processes:
                proc = self._processes[norm_key]
                if proc.poll() is not None:
                    info.status = "STOPPED" if proc.returncode == 0 else f"EXITED ({proc.returncode})"
            return info

    def get_logs(self, worktree_path: Path, tail: int = 100) -> List[str]:
        """Retrieve recent console log lines."""
        norm_key = str(worktree_path.resolve())
        with self._lock:
            d = self._logs.get(norm_key)
            if not d:
                return []
            lines = list(d)
            return lines[-tail:] if tail < len(lines) else lines

    def stop_all(self) -> None:
        """Stop all supervised processes."""
        with self._lock:
            for key, proc in list(self._processes.items()):
                if proc.poll() is None:
                    if sys.platform == "win32":
                        subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True)
                    else:
                        proc.terminate()
