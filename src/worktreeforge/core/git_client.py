"""Git CLI subprocess wrapper and parser for worktrees and stashes."""

from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple

from worktreeforge.core.models import (
    StashDiff,
    StashEntry,
    StashFileChange,
    WorktreeInfo,
)


class GitError(Exception):
    """Exception raised when a git command fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class GitClient:
    """Wrapper around Git CLI subprocess commands."""

    def __init__(self, cwd: Optional[Path] = None):
        self.cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()

    def run(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
        timeout: int = 30,
    ) -> Tuple[int, str, str]:
        """Execute a git command with UTF-8 encoding."""
        target_dir = str(cwd or self.cwd)
        cmd = ["git"] + args
        try:
            res = subprocess.run(
                cmd,
                cwd=target_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if check and res.returncode != 0:
                raise GitError(
                    f"Git command failed: {' '.join(cmd)}\n{res.stderr.strip()}",
                    returncode=res.returncode,
                    stderr=res.stderr.strip(),
                )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"Git command timed out: {' '.join(cmd)}") from exc
        except FileNotFoundError as exc:
            raise GitError("git executable not found in PATH") from exc

    def get_repo_root(self, path: Optional[Path] = None) -> Path:
        """Find the root directory of the current repository."""
        _, stdout, _ = self.run(["rev-parse", "--show-toplevel"], cwd=path or self.cwd)
        root = stdout.strip()
        if not root:
            raise GitError("Not a git repository (or any parent directory)")
        return Path(root).resolve()

    def branch_exists(self, branch: str, cwd: Optional[Path] = None) -> bool:
        """Check if a local branch exists."""
        code, _, _ = self.run(
            ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=cwd,
            check=False,
        )
        return code == 0

    def list_worktrees(self, cwd: Optional[Path] = None) -> List[WorktreeInfo]:
        """Parse worktrees from git worktree list --porcelain."""
        _, stdout, _ = self.run(["worktree", "list", "--porcelain"], cwd=cwd)
        worktrees: List[WorktreeInfo] = []
        blocks = stdout.strip().split("\n\n")

        for idx, block in enumerate(blocks):
            if not block.strip():
                continue
            lines = [line.strip() for line in block.split("\n") if line.strip()]

            path_val: Optional[str] = None
            commit_hash = ""
            branch_val = ""
            is_bare = False
            is_locked = False
            lock_reason: Optional[str] = None

            for line in lines:
                if line.startswith("worktree "):
                    path_val = line[len("worktree ") :].strip()
                elif line.startswith("HEAD "):
                    commit_hash = line[len("HEAD ") :].strip()
                elif line.startswith("branch "):
                    raw_branch = line[len("branch ") :].strip()
                    if raw_branch.startswith("refs/heads/"):
                        branch_val = raw_branch[len("refs/heads/") :]
                    else:
                        branch_val = raw_branch
                elif line == "bare":
                    is_bare = True
                elif line.startswith("locked"):
                    is_locked = True
                    reason_part = line[len("locked") :].strip()
                    lock_reason = reason_part if reason_part else None
                elif line == "detached":
                    branch_val = "detached"

            if path_val:
                is_main = idx == 0
                dirty, uncommitted = self.check_dirty(Path(path_val))

                worktrees.append(
                    WorktreeInfo(
                        path=str(Path(path_val).resolve()),
                        commit_hash=commit_hash,
                        branch=branch_val or "HEAD",
                        is_bare=is_bare,
                        is_locked=is_locked,
                        lock_reason=lock_reason,
                        is_main=is_main,
                        is_dirty=dirty,
                        uncommitted_files=uncommitted,
                    )
                )

        return worktrees

    def check_dirty(
        self, path: Path, ignored_patterns: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """Check for uncommitted or untracked changes in a worktree path."""
        if not path.exists():
            return False, []
        code, stdout, _ = self.run(
            ["status", "--porcelain"],
            cwd=path,
            check=False,
        )
        if code != 0:
            return False, []

        ignored = ignored_patterns if ignored_patterns is not None else [
            ".env.local",
            ".worktreeforge.ports.json",
            ".worktreeforge.yaml",
            ".worktreeforge.yml",
        ]
        files = []
        for line in stdout.strip().splitlines():
            if len(line) >= 3:
                fname = line[3:].strip()
                if not any(fname == ig or fname.endswith("/" + ig) or fname.endswith("\\" + ig) for ig in ignored):
                    files.append(fname)

        return len(files) > 0, files

    def add_worktree(
        self,
        path: Path,
        branch: str,
        base_ref: Optional[str] = None,
        new_branch: bool = True,
        cwd: Optional[Path] = None,
    ) -> WorktreeInfo:
        """Create a new worktree directory and checkout/create branch."""
        target_path = str(path.resolve())

        # Check if local branch already exists
        exists = self.branch_exists(branch, cwd=cwd)

        cmd = ["worktree", "add"]
        if exists or not new_branch:
            cmd.extend([target_path, branch])
        else:
            cmd.extend(["-b", branch, target_path])
            if base_ref:
                cmd.append(base_ref)

        self.run(cmd, cwd=cwd)

        # Refresh and return the created worktree
        worktrees = self.list_worktrees(cwd=cwd)
        for wt in worktrees:
            if wt.path == target_path:
                return wt

        # Fallback return
        return WorktreeInfo(
            path=target_path,
            commit_hash="",
            branch=branch,
            is_main=False,
        )

    def remove_worktree(
        self, path: Path, force: bool = False, cwd: Optional[Path] = None
    ) -> None:
        """Remove a worktree directory."""
        target_path = str(path.resolve())
        cmd = ["worktree", "remove", target_path]
        if force:
            cmd.append("--force")
        self.run(cmd, cwd=cwd)

    def lock_worktree(
        self, path: Path, reason: Optional[str] = None, cwd: Optional[Path] = None
    ) -> None:
        """Lock a worktree against accidental removal."""
        cmd = ["worktree", "lock", str(path.resolve())]
        if reason:
            cmd.extend(["--reason", reason])
        self.run(cmd, cwd=cwd)

    def unlock_worktree(self, path: Path, cwd: Optional[Path] = None) -> None:
        """Unlock a locked worktree."""
        self.run(["worktree", "unlock", str(path.resolve())], cwd=cwd)

    def prune_worktrees(self, cwd: Optional[Path] = None) -> None:
        """Prune stale worktree information from .git/worktrees."""
        self.run(["worktree", "prune"], cwd=cwd)

    def delete_branch(
        self, branch: str, force: bool = False, cwd: Optional[Path] = None
    ) -> None:
        """Delete a local git branch."""
        flag = "-D" if force else "-d"
        self.run(["branch", flag, branch], cwd=cwd)

    # -------------------------------------------------------------------------
    # Stash Management
    # -------------------------------------------------------------------------

    def list_stashes(self, cwd: Optional[Path] = None) -> List[StashEntry]:
        """List all stashes with metadata and touched files count."""
        format_str = "%gd|%h|%an|%ci|%s"
        _, stdout, _ = self.run(
            ["stash", "list", f"--pretty=format:{format_str}"],
            cwd=cwd,
        )
        stashes: List[StashEntry] = []
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]

        for line in lines:
            parts = line.split("|")
            if len(parts) < 5:
                continue
            stash_id = parts[0]  # stash@{0}
            commit_hash = parts[1]
            author = parts[2]
            date_str = parts[3]
            subject = "|".join(parts[4:])

            # Extract index
            index = 0
            if "{" in stash_id and "}" in stash_id:
                try:
                    index = int(stash_id.split("{")[1].split("}")[0])
                except ValueError:
                    index = len(stashes)

            # Extract branch from subject if formatted e.g. "WIP on branch: ..." or "On branch: ..."
            branch_hint = "unknown"
            if " on " in subject:
                branch_candidate = subject.split(" on ")[1].split(":")[0].strip()
                if branch_candidate:
                    branch_hint = branch_candidate
            elif "On " in subject:
                branch_candidate = subject.split("On ")[1].split(":")[0].strip()
                if branch_candidate:
                    branch_hint = branch_candidate

            # Get stat summary
            files_changed = self._get_stash_files(index, cwd=cwd)

            stashes.append(
                StashEntry(
                    index=index,
                    id=stash_id,
                    hash=commit_hash,
                    message=subject,
                    branch=branch_hint,
                    author=author,
                    date=date_str,
                    files=files_changed,
                )
            )

        return stashes

    def _get_stash_files(
        self, index: int, cwd: Optional[Path] = None
    ) -> List[StashFileChange]:
        """Fetch files changed in a specific stash using numstat."""
        code, stdout, _ = self.run(
            ["stash", "show", "--numstat", f"stash@{{{index}}}"],
            cwd=cwd,
            check=False,
        )
        if code != 0:
            return []
        changes: List[StashFileChange] = []
        for line in stdout.splitlines():
            parts = line.strip().split("\t")
            if len(parts) == 3:
                ins_str, del_str, file_path = parts
                ins = int(ins_str) if ins_str.isdigit() else 0
                dels = int(del_str) if del_str.isdigit() else 0
                changes.append(
                    StashFileChange(
                        path=file_path,
                        status="M",
                        insertions=ins,
                        deletions=dels,
                    )
                )
        return changes

    def get_stash_diff(self, index: int, cwd: Optional[Path] = None) -> StashDiff:
        """Fetch unified patch diff for a stash item and partition per file."""
        stash_id = f"stash@{{{index}}}"
        _, stdout, _ = self.run(["stash", "show", "-p", stash_id], cwd=cwd)
        raw_diff = stdout

        # Partition by file
        files_map: Dict[str, str] = {}
        chunks = raw_diff.split("diff --git ")
        for chunk in chunks:
            if not chunk.strip():
                continue
            lines = chunk.splitlines()
            first_line = lines[0]
            # e.g. "a/file.txt b/file.txt"
            parts = first_line.split(" ")
            if len(parts) >= 2:
                file_target = parts[1]
                if file_target.startswith("b/"):
                    file_target = file_target[2:]
                files_map[file_target] = "diff --git " + chunk

        return StashDiff(
            stash_index=index,
            stash_id=stash_id,
            raw_diff=raw_diff,
            files=files_map,
        )

    def apply_stash(self, index: int, cwd: Optional[Path] = None) -> None:
        """Apply stash to current working tree."""
        self.run(["stash", "apply", f"stash@{{{index}}}"], cwd=cwd)

    def pop_stash(self, index: int, cwd: Optional[Path] = None) -> None:
        """Apply and drop stash from stack."""
        self.run(["stash", "pop", f"stash@{{{index}}}"], cwd=cwd)

    def drop_stash(self, index: int, cwd: Optional[Path] = None) -> None:
        """Drop stash item."""
        self.run(["stash", "drop", f"stash@{{{index}}}"], cwd=cwd)

    def branch_from_stash(
        self, index: int, branch_name: str, cwd: Optional[Path] = None
    ) -> None:
        """Create and checkout new branch from stash, then drop stash."""
        self.run(["stash", "branch", branch_name, f"stash@{{{index}}}"], cwd=cwd)
