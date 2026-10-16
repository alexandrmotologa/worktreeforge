"""Creates and manages directory junctions and symlinks for build caches and dependencies."""

import os
from pathlib import Path
import subprocess
import sys
from typing import List, Optional


DEFAULT_TARGET_DIRS = [
    "node_modules",
    ".venv",
    "venv",
    ".next/cache",
    ".turbo",
    "target",
]


class DependencyLinker:
    """Manages fast cross-worktree directory junctions and symlinks."""

    @staticmethod
    def detect_shareable(source_dir: Path, candidates: Optional[List[str]] = None) -> List[str]:
        """Detect which dependency directories exist in the source repository."""
        check_list = candidates or DEFAULT_TARGET_DIRS
        found: List[str] = []
        for rel in check_list:
            candidate = source_dir / rel
            if candidate.is_dir():
                found.append(rel)
        return found

    @staticmethod
    def create_link(source_target: Path, dest_link: Path) -> bool:
        """Create directory junction (Windows) or symbolic link (Unix)."""
        if not source_target.is_dir() or dest_link.exists():
            return False

        dest_link.parent.mkdir(parents=True, exist_ok=True)

        if sys.platform == "win32":
            # Prefer Windows Directory Junction (mklink /J)
            try:
                # Use Windows built-in mklink via cmd.exe
                cmd = f'mklink /J "{str(dest_link)}" "{str(source_target)}"'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    return True
            except Exception:
                pass

            # Fallback to os.symlink
            try:
                os.symlink(str(source_target), str(dest_link), target_is_directory=True)
                return True
            except (OSError, NotImplementedError):
                return False
        else:
            try:
                os.symlink(str(source_target), str(dest_link), target_is_directory=True)
                return True
            except OSError:
                return False

    @classmethod
    def link_worktree(
        cls,
        repo_root: Path,
        worktree_path: Path,
        targets: Optional[List[str]] = None,
    ) -> List[str]:
        """Link available dependencies into the target worktree."""
        shareable = cls.detect_shareable(repo_root, targets)
        linked: List[str] = []

        for rel_dir in shareable:
            src = repo_root / rel_dir
            dst = worktree_path / rel_dir
            if not dst.exists():
                success = cls.create_link(src, dst)
                if success:
                    linked.append(rel_dir)

        return linked

    @staticmethod
    def unlink_worktree(worktree_path: Path, targets: Optional[List[str]] = None) -> List[str]:
        """Safely remove directory junctions / symlinks without deleting original target data."""
        check_list = targets or DEFAULT_TARGET_DIRS
        unlinked: List[str] = []

        for rel_dir in check_list:
            dst = worktree_path / rel_dir
            if dst.is_symlink() or (sys.platform == "win32" and dst.is_dir()):
                try:
                    if dst.is_symlink():
                        dst.unlink()
                        unlinked.append(rel_dir)
                    elif sys.platform == "win32":
                        # For Windows directory junctions, rmdir safely unlinks without touching target files
                        subprocess.run(f'rmdir "{str(dst)}"', shell=True, capture_output=True)
                        if not dst.exists():
                            unlinked.append(rel_dir)
                except Exception:
                    pass

        return unlinked
