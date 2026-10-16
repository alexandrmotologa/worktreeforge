"""Tests for GitHub PR status checker."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from worktreeforge.core.models import PRState
from worktreeforge.github.pr_checker import GitHubPRChecker


def test_pr_checker_fallback():
    checker = GitHubPRChecker()
    # Main branches should return NONE immediately
    status = checker.get_pr_status("main")
    assert status.state == PRState.NONE

    status_master = checker.get_pr_status("master")
    assert status_master.state == PRState.NONE


def test_pr_checker_mocked_merged():
    checker = GitHubPRChecker()

    mock_json = '{"state": "MERGED", "number": 42, "url": "https://github.com/org/repo/pull/42", "title": "Add Auth", "mergedAt": "2026-10-15T12:00:00Z"}'

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_json)
        with patch.object(checker, "is_gh_available", return_value=True):
            status = checker.get_pr_status("feature/auth")
            assert status.state == PRState.MERGED
            assert status.number == 42
            assert status.title == "Add Auth"
