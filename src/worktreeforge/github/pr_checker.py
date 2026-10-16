"""Interrogates GitHub CLI for PR statuses and merged state."""

import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Dict, Optional, Tuple

from worktreeforge.core.models import PRState, PRStatus


class GitHubPRChecker:
    """Interrogates GitHub CLI for PR statuses with in-memory caching."""

    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Tuple[float, PRStatus]] = {}
        self._gh_available: Optional[bool] = None

    def is_gh_available(self) -> bool:
        """Check if gh executable is present on system PATH."""
        if self._gh_available is None:
            self._gh_available = shutil.which("gh") is not None
        return self._gh_available

    def get_pr_status(
        self, branch: str, cwd: Optional[Path] = None, force_refresh: bool = False
    ) -> PRStatus:
        """Fetch PR status for the given branch."""
        if not branch or branch in ("HEAD", "main", "master", "detached"):
            return PRStatus(state=PRState.NONE)

        cache_key = f"{str(cwd)}:{branch}"
        now = time.time()

        if not force_refresh and cache_key in self._cache:
            timestamp, cached_status = self._cache[cache_key]
            if now - timestamp < self.cache_ttl:
                return cached_status

        if not self.is_gh_available():
            return PRStatus(state=PRState.NONE)

        status = self._query_gh(branch, cwd=cwd)
        self._cache[cache_key] = (now, status)
        return status

    def _query_gh(self, branch: str, cwd: Optional[Path] = None) -> PRStatus:
        """Run gh pr view command."""
        cmd = [
            "gh",
            "pr",
            "view",
            branch,
            "--json",
            "state,number,url,title,mergedAt",
        ]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if res.returncode != 0:
                return PRStatus(state=PRState.NONE)

            data = json.loads(res.stdout)
            state_raw = str(data.get("state", "NONE")).upper()

            state = PRState.NONE
            if state_raw == "MERGED":
                state = PRState.MERGED
            elif state_raw == "OPEN":
                state = PRState.OPEN
            elif state_raw == "CLOSED":
                state = PRState.CLOSED
            elif state_raw == "DRAFT":
                state = PRState.DRAFT

            return PRStatus(
                state=state,
                number=data.get("number"),
                url=data.get("url"),
                title=data.get("title"),
                merged_at=data.get("mergedAt"),
            )
        except Exception:
            return PRStatus(state=PRState.NONE)
