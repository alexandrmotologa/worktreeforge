"""Allocates non-conflicting port offsets and tracks registry state."""

import json
from pathlib import Path
import socket
from typing import Dict, List, Optional, Set

from worktreeforge.core.models import (
    PortAllocation,
    PortMultiplexerConfig,
    PortRegistry,
)


REGISTRY_FILE_NAME = ".worktreeforge.ports.json"


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Verify that a TCP port is free to bind on localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.bind((host, port))
            return True
    except OSError:
        return False


class PortAllocator:
    """Manages port reservation and registry persistence."""

    def __init__(self, repo_root: Path, config: Optional[PortMultiplexerConfig] = None):
        self.repo_root = Path(repo_root).resolve()
        self.config = config or PortMultiplexerConfig()
        self.registry_path = self.repo_root / REGISTRY_FILE_NAME
        self.registry = self._load_registry()

    def _load_registry(self) -> PortRegistry:
        """Load persistent port allocations from disk."""
        if self.registry_path.is_file():
            try:
                content = self.registry_path.read_text(encoding="utf-8")
                data = json.loads(content)
                return PortRegistry.model_validate(data)
            except Exception:
                pass
        return PortRegistry()

    def _save_registry(self) -> None:
        """Save allocations to repository root."""
        content = self.registry.model_dump_json(indent=2)
        self.registry_path.write_text(content, encoding="utf-8")

    def get_assigned_ports_set(self) -> Set[int]:
        """Return all ports currently assigned in the registry."""
        return {a.allocated_port for a in self.registry.allocations if a.is_active}

    def allocate_ports(
        self,
        worktree_path: Path,
        branch: str,
        detected_ports: Dict[str, int],
        explicit_offset: Optional[int] = None,
    ) -> List[PortAllocation]:
        """Allocate collision-free ports for a worktree directory."""
        norm_path = str(worktree_path.resolve())
        allocations: List[PortAllocation] = []
        assigned_in_registry = self.get_assigned_ports_set()

        # Check existing allocations for this worktree path
        existing_for_path = {
            a.port_variable: a for a in self.registry.find_allocations_for_path(norm_path)
        }

        # Determine next base offset if not explicit
        if explicit_offset is not None:
            base_offset = explicit_offset
        else:
            # Count other registered active worktrees
            other_active_paths = {
                a.worktree_path
                for a in self.registry.allocations
                if a.worktree_path != norm_path and a.is_active
            }
            base_offset = len(other_active_paths) + self.config.start_offset

        for var_name, base_port in detected_ports.items():
            # If already assigned and still matches, keep it
            if var_name in existing_for_path:
                allocations.append(existing_for_path[var_name])
                continue

            candidate = base_port + base_offset
            # Ensure candidate is within allowed range and not in registry or in-use socket
            while (
                candidate in assigned_in_registry
                or not is_port_available(candidate)
            ):
                candidate += 1
                if candidate > self.config.port_range_max:
                    candidate = self.config.port_range_min

            allocation = PortAllocation(
                worktree_path=norm_path,
                branch=branch,
                port_variable=var_name,
                base_port=base_port,
                allocated_port=candidate,
                is_active=True,
            )
            allocations.append(allocation)
            assigned_in_registry.add(candidate)

        # Update registry
        self.registry.remove_for_path(norm_path)
        self.registry.allocations.extend(allocations)
        self._save_registry()

        return allocations

    def release_ports_for_path(self, worktree_path: Path) -> List[PortAllocation]:
        """Remove port reservations for a deleted worktree."""
        norm_path = str(worktree_path.resolve())
        removed = self.registry.remove_for_path(norm_path)
        self._save_registry()
        return removed

    def get_allocations_for_path(self, worktree_path: Path) -> Dict[str, int]:
        """Return dict of var_name -> allocated_port for a worktree path."""
        norm_path = str(worktree_path.resolve())
        return {
            a.port_variable: a.allocated_port
            for a in self.registry.find_allocations_for_path(norm_path)
        }

    def list_all_allocations(self) -> List[PortAllocation]:
        """Return list of all allocations."""
        return self.registry.allocations
