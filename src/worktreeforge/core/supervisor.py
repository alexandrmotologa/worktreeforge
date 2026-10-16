"""Worktree supervisor coordinating Git operations, port allocation, and PR checks."""

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from worktreeforge.core.config import load_config
from worktreeforge.core.git_client import GitClient, GitError
from worktreeforge.core.models import (
    AppConfig,
    PortAllocation,
    PRState,
    WorktreeInfo,
)
from worktreeforge.github.pr_checker import GitHubPRChecker
from worktreeforge.multiplexer.env_patcher import EnvPatcher
from worktreeforge.multiplexer.port_allocator import PortAllocator
from worktreeforge.multiplexer.port_scanner import PortScanner
from worktreeforge.stash.inspector import StashInspector


class SupervisorError(Exception):
    """Exception raised for supervisor lifecycle or validation errors."""
    pass


class WorktreeSupervisor:
    """High-level supervisor coordinating worktrees, ports, stashes, and PR sync."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        config: Optional[AppConfig] = None,
        git_client: Optional[GitClient] = None,
    ):
        self.git = git_client or GitClient(cwd=repo_root)
        self.repo_root = repo_root or self.git.get_repo_root()
        self.config = config or load_config(self.repo_root)
        self.port_scanner = PortScanner(config=self.config.port_multiplexer)
        self.port_allocator = PortAllocator(
            repo_root=self.repo_root, config=self.config.port_multiplexer
        )
        self.env_patcher = EnvPatcher(
            output_filename=self.config.port_multiplexer.output_env_file
        )
        self.pr_checker = GitHubPRChecker()
        self.stash_inspector = StashInspector(git_client=self.git, cwd=self.repo_root)

    def list_worktrees(
        self, enrich_ports: bool = True, enrich_pr: bool = True
    ) -> List[WorktreeInfo]:
        """Fetch all worktrees with active ports and GitHub PR states."""
        worktrees = self.git.list_worktrees(cwd=self.repo_root)

        for wt in worktrees:
            # 1. Enrich ports
            if enrich_ports:
                allocations = self.port_allocator.get_allocations_for_path(Path(wt.path))
                wt.active_ports = allocations

            # 2. Enrich PR status
            if enrich_pr and not wt.is_main and wt.branch:
                wt.pr_status = self.pr_checker.get_pr_status(
                    wt.branch, cwd=Path(wt.path)
                )

        return worktrees

    def find_worktree(self, identifier: str) -> Optional[WorktreeInfo]:
        """Locate worktree by branch name, folder name, or absolute path."""
        worktrees = self.list_worktrees(enrich_ports=True, enrich_pr=False)
        norm_ident = identifier.strip().lower()

        for wt in worktrees:
            if wt.branch.lower() == norm_ident:
                return wt
            if Path(wt.path).name.lower() == norm_ident:
                return wt
            try:
                if Path(wt.path).resolve() == Path(identifier).resolve():
                    return wt
            except Exception:
                pass

        return None

    def compute_worktree_path(self, branch: str) -> Path:
        """Calculate path for a new worktree using configuration template."""
        branch_slug = re.sub(r"[/\\:\*\?\"<>\|]", "-", branch).strip("-")
        repo_name = self.repo_root.name

        dir_template = self.config.worktrees_dir
        rel_or_abs = dir_template.format(
            repo=repo_name,
            branch=branch,
            branch_slug=branch_slug,
        )

        candidate = (self.repo_root / rel_or_abs).resolve()
        return candidate

    def create_worktree(
        self,
        branch: str,
        base_ref: Optional[str] = None,
        target_path: Optional[Path] = None,
        port_offset: Optional[int] = None,
        configure_ports: bool = True,
    ) -> Tuple[WorktreeInfo, List[PortAllocation]]:
        """Create a new worktree, assign non-conflicting ports, and patch env."""
        dest_path = target_path or self.compute_worktree_path(branch)

        if dest_path.exists():
            raise SupervisorError(f"Target directory already exists: {dest_path}")

        # Execute git worktree add
        wt_info = self.git.add_worktree(
            path=dest_path,
            branch=branch,
            base_ref=base_ref,
            new_branch=True,
            cwd=self.repo_root,
        )

        allocations: List[PortAllocation] = []
        if configure_ports and self.config.port_multiplexer.enabled:
            # Detect ports from main repo
            detected_ports = self.port_scanner.scan_directory(self.repo_root)

            # Allocate deterministic non-conflicting ports
            allocations = self.port_allocator.allocate_ports(
                worktree_path=dest_path,
                branch=branch,
                detected_ports=detected_ports,
                explicit_offset=port_offset,
            )

            # Patch .env.local
            ports_map = {a.port_variable: a.allocated_port for a in allocations}
            self.env_patcher.patch_worktree(
                worktree_path=dest_path,
                branch=branch,
                ports=ports_map,
            )
            wt_info.active_ports = ports_map

        # Run post-create hooks if configured
        for hook_cmd in self.config.hooks.post_create:
            try:
                subprocess.run(
                    hook_cmd,
                    shell=True,
                    cwd=str(dest_path),
                    check=False,
                    timeout=60,
                )
            except Exception:
                pass

        return wt_info, allocations

    def remove_worktree(
        self,
        identifier: str,
        force: bool = False,
        delete_branch: bool = False,
    ) -> Tuple[WorktreeInfo, List[PortAllocation]]:
        """Safely remove a worktree directory and clean up port reservations."""
        wt = self.find_worktree(identifier)
        if not wt:
            raise SupervisorError(f"Worktree not found for identifier: '{identifier}'")

        if wt.is_main:
            raise SupervisorError("Cannot remove the primary repository worktree")

        if wt.is_locked and not force:
            reason_msg = f" (Reason: {wt.lock_reason})" if wt.lock_reason else ""
            raise SupervisorError(
                f"Worktree is locked{reason_msg}. Unlock first with 'worktreeforge unlock {wt.branch}'"
            )

        # Check dirty state
        if wt.is_dirty and not force:
            uncommitted = ", ".join(wt.uncommitted_files[:3])
            raise SupervisorError(
                f"Worktree has uncommitted changes ({uncommitted}). Use --force to delete."
            )

        # Run pre-remove hooks
        target_path = Path(wt.path)
        if target_path.exists():
            for hook_cmd in self.config.hooks.pre_remove:
                try:
                    subprocess.run(
                        hook_cmd,
                        shell=True,
                        cwd=str(target_path),
                        check=False,
                        timeout=30,
                    )
                except Exception:
                    pass

        # Clean up tool-managed output env file if it exists
        managed_env = target_path / self.config.port_multiplexer.output_env_file
        if managed_env.is_file():
            try:
                managed_env.unlink()
            except OSError:
                pass

        # Release ports
        released_allocations = self.port_allocator.release_ports_for_path(target_path)

        # Git remove
        git_remove_force = force or (not wt.is_dirty)
        self.git.remove_worktree(target_path, force=git_remove_force, cwd=self.repo_root)
        self.git.prune_worktrees(cwd=self.repo_root)

        # Delete branch if requested
        if delete_branch and wt.branch and wt.branch != "HEAD":
            try:
                self.git.delete_branch(wt.branch, force=force, cwd=self.repo_root)
            except GitError:
                pass

        return wt, released_allocations

    def lock_worktree(self, identifier: str, reason: Optional[str] = None) -> WorktreeInfo:
        """Lock worktree to prevent accidental deletion."""
        wt = self.find_worktree(identifier)
        if not wt:
            raise SupervisorError(f"Worktree not found: '{identifier}'")
        self.git.lock_worktree(Path(wt.path), reason=reason, cwd=self.repo_root)
        wt.is_locked = True
        wt.lock_reason = reason
        return wt

    def unlock_worktree(self, identifier: str) -> WorktreeInfo:
        """Unlock a locked worktree."""
        wt = self.find_worktree(identifier)
        if not wt:
            raise SupervisorError(f"Worktree not found: '{identifier}'")
        self.git.unlock_worktree(Path(wt.path), cwd=self.repo_root)
        wt.is_locked = False
        wt.lock_reason = None
        return wt

    def prune_merged_worktrees(
        self, dry_run: bool = False
    ) -> List[Tuple[WorktreeInfo, bool, str]]:
        """Identify worktrees with merged GitHub PRs and clean them up."""
        worktrees = self.list_worktrees(enrich_ports=True, enrich_pr=True)
        results: List[Tuple[WorktreeInfo, bool, str]] = []

        for wt in worktrees:
            if wt.is_main:
                continue
            if wt.is_locked and self.config.pruner.protect_locked:
                continue

            if wt.pr_status and wt.pr_status.state == PRState.MERGED:
                if wt.is_dirty and self.config.pruner.require_clean_git:
                    results.append(
                        (wt, False, "Skipped: worktree contains uncommitted changes")
                    )
                    continue

                if dry_run:
                    results.append((wt, True, "Would be removed (dry-run)"))
                else:
                    try:
                        self.remove_worktree(
                            wt.path,
                            force=False,
                            delete_branch=self.config.pruner.delete_branch_on_prune,
                        )
                        results.append((wt, True, "Successfully removed"))
                    except Exception as e:
                        results.append((wt, False, f"Failed to remove: {str(e)}"))

        return results

    def open_editor(self, path: Path) -> bool:
        """Launch configured or detected code editor in worktree path."""
        editor_cmd = self.config.editor.command.strip()
        if not editor_cmd:
            for candidate in ["code", "cursor", "code-insiders"]:
                if shutil.which(candidate):
                    editor_cmd = candidate
                    break

        if not editor_cmd:
            return False

        try:
            subprocess.Popen(
                [editor_cmd, str(path)],
                cwd=str(path),
                shell=os.name == "nt",
            )
            return True
        except Exception:
            return False
