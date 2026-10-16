"""Stash inspection, diff breakdown, and search engine."""

from pathlib import Path
from typing import List, Optional, Tuple

from worktreeforge.core.git_client import GitClient
from worktreeforge.core.models import StashDiff, StashEntry


class StashInspector:
    """Provides high-level stash browsing and full-text search capabilities."""

    def __init__(self, git_client: Optional[GitClient] = None, cwd: Optional[Path] = None):
        self.git = git_client or GitClient(cwd=cwd)
        self.cwd = cwd or self.git.cwd

    def list_all(self) -> List[StashEntry]:
        """List all stashes in chronological stack order."""
        return self.git.list_stashes(cwd=self.cwd)

    def get_diff(self, index: int) -> StashDiff:
        """Fetch unified diff partitioned by file."""
        return self.git.get_stash_diff(index=index, cwd=self.cwd)

    def search(self, query: str) -> List[Tuple[StashEntry, List[str]]]:
        """Search stashes across commit message, author, branch, and diff contents."""
        q = query.strip().lower()
        if not q:
            return [(s, []) for s in self.list_all()]

        results: List[Tuple[StashEntry, List[str]]] = []
        all_stashes = self.list_all()

        for stash in all_stashes:
            matches: List[str] = []
            if q in stash.message.lower():
                matches.append(f"Message: {stash.message}")
            if q in stash.branch.lower():
                matches.append(f"Branch: {stash.branch}")
            if q in stash.author.lower():
                matches.append(f"Author: {stash.author}")

            for f in stash.files:
                if q in f.path.lower():
                    matches.append(f"File path: {f.path}")

            # If not yet matched, check diff content
            if not matches:
                diff = self.get_diff(stash.index)
                if q in diff.raw_diff.lower():
                    # Find snippet line
                    for line in diff.raw_diff.splitlines():
                        if q in line.lower() and (
                            line.startswith("+") or line.startswith("-")
                        ):
                            matches.append(f"Diff: {line.strip()[:80]}")
                            break

            if matches:
                results.append((stash, matches))

        return results

    def apply(self, index: int, drop: bool = False) -> None:
        """Apply stash to current tree, optionally dropping it."""
        if drop:
            self.git.pop_stash(index, cwd=self.cwd)
        else:
            self.git.apply_stash(index, cwd=self.cwd)

    def drop(self, index: int) -> None:
        """Drop a stash entry."""
        self.git.drop_stash(index, cwd=self.cwd)

    def branch(self, index: int, branch_name: str) -> None:
        """Create a new branch from stash and drop stash."""
        self.git.branch_from_stash(index, branch_name, cwd=self.cwd)
