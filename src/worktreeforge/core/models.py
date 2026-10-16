"""Data models and schemas for WorktreeForge."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PRState(str, Enum):
    """GitHub Pull Request states."""

    OPEN = "OPEN"
    MERGED = "MERGED"
    CLOSED = "CLOSED"
    DRAFT = "DRAFT"
    NONE = "NONE"


class PRStatus(BaseModel):
    """GitHub Pull Request status summary."""

    state: PRState = PRState.NONE
    number: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    merged_at: Optional[str] = None


class PortAllocation(BaseModel):
    """Port assigned to a worktree instance."""

    worktree_path: str
    branch: str
    port_variable: str
    base_port: int
    allocated_port: int
    is_active: bool = True
    process_pid: Optional[int] = None


class PortRegistry(BaseModel):
    """Persistent storage format for allocated ports."""

    version: int = 1
    allocations: List[PortAllocation] = Field(default_factory=list)

    def find_allocations_for_path(self, path: str) -> List[PortAllocation]:
        norm_target = str(Path(path).resolve())
        return [
            a
            for a in self.allocations
            if str(Path(a.worktree_path).resolve()) == norm_target and a.is_active
        ]

    def find_allocations_for_branch(self, branch: str) -> List[PortAllocation]:
        return [a for a in self.allocations if a.branch == branch and a.is_active]

    def remove_for_path(self, path: str) -> List[PortAllocation]:
        norm_target = str(Path(path).resolve())
        removed = [
            a
            for a in self.allocations
            if str(Path(a.worktree_path).resolve()) == norm_target
        ]
        self.allocations = [
            a
            for a in self.allocations
            if str(Path(a.worktree_path).resolve()) != norm_target
        ]
        return removed


class ProcessInfo(BaseModel):
    """Information regarding a background dev server run."""

    worktree_path: str
    branch: str
    command: str
    pid: int
    status: str = "RUNNING"
    started_at: str = ""


class WorktreeInfo(BaseModel):
    """Information representing a single Git worktree."""

    path: str
    commit_hash: str
    branch: str
    is_bare: bool = False
    is_locked: bool = False
    lock_reason: Optional[str] = None
    is_main: bool = False
    is_dirty: bool = False
    uncommitted_files: List[str] = Field(default_factory=list)
    active_ports: Dict[str, int] = Field(default_factory=dict)
    pr_status: Optional[PRStatus] = None
    created_at: Optional[str] = None
    linked_dependencies: List[str] = Field(default_factory=list)
    process: Optional[ProcessInfo] = None
    http_ready: bool = False

    @property
    def display_name(self) -> str:
        name = Path(self.path).name
        return name if name else self.branch


class StashFileChange(BaseModel):
    """File touched in a stash commit."""

    path: str
    status: str = "M"
    insertions: int = 0
    deletions: int = 0


class StashEntry(BaseModel):
    """Summary of a git stash item."""

    index: int
    id: str
    hash: str
    message: str
    branch: str
    author: str
    date: str
    files: List[StashFileChange] = Field(default_factory=list)


class StashDiff(BaseModel):
    """Diff content associated with a stash item."""

    stash_index: int
    stash_id: str
    raw_diff: str
    files: Dict[str, str] = Field(default_factory=dict)


class BranchComparison(BaseModel):
    """Comparison results between two branches."""

    base_branch: str
    target_branch: str
    ahead_count: int = 0
    behind_count: int = 0
    commits: List[Dict[str, str]] = Field(default_factory=list)
    changed_files: List[Dict[str, Any]] = Field(default_factory=list)
    unified_diff: str = ""


class PortMultiplexerConfig(BaseModel):
    """Configuration for port multiplexing behavior."""

    enabled: bool = True
    start_offset: int = 1
    port_range_min: int = 3000
    port_range_max: int = 9999
    scan_env_files: List[str] = Field(
        default_factory=lambda: [".env", ".env.example", ".env.local"]
    )
    scan_package_json: bool = True
    port_variables: List[str] = Field(
        default_factory=lambda: [
            "PORT",
            "VITE_PORT",
            "NEXT_PUBLIC_PORT",
            "SERVER_PORT",
            "API_PORT",
            "CLIENT_PORT",
            "APP_PORT",
            "FASTAPI_PORT",
            "UVICORN_PORT",
            "WEB_PORT",
        ]
    )
    output_env_file: str = ".env.local"


class DependencyConfig(BaseModel):
    """Configuration for automatic dependency linking."""

    enabled: bool = False
    targets: List[str] = Field(
        default_factory=lambda: [
            "node_modules",
            ".venv",
            "venv",
            ".next/cache",
            ".turbo",
            "target",
        ]
    )


class SubmoduleConfig(BaseModel):
    """Configuration for Git submodule handling."""

    auto_init: bool = True
    use_reference: bool = True


class ProcessConfig(BaseModel):
    """Configuration for dev server process runner."""

    default_command: str = ""
    auto_stop_on_remove: bool = True


class PrunerConfig(BaseModel):
    """Configuration for worktree pruning."""

    require_clean_git: bool = True
    check_github_pr: bool = True
    delete_branch_on_prune: bool = False
    protect_locked: bool = True


class EditorConfig(BaseModel):
    """Editor integration preferences."""

    command: str = ""


class HooksConfig(BaseModel):
    """Lifecycle hook commands."""

    post_create: List[str] = Field(default_factory=list)
    pre_remove: List[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Top-level WorktreeForge configuration."""

    version: int = 1
    worktrees_dir: str = "../{repo}-{branch_slug}"
    port_multiplexer: PortMultiplexerConfig = Field(
        default_factory=PortMultiplexerConfig
    )
    dependencies: DependencyConfig = Field(default_factory=DependencyConfig)
    submodules: SubmoduleConfig = Field(default_factory=SubmoduleConfig)
    process: ProcessConfig = Field(default_factory=ProcessConfig)
    pruner: PrunerConfig = Field(default_factory=PrunerConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
