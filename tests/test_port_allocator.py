"""Tests for port allocation and socket verification."""

from pathlib import Path
from worktreeforge.multiplexer.port_allocator import (
    PortAllocator,
    is_port_available,
)


def test_socket_availability():
    # Ephemeral free port test
    assert is_port_available(59123) is True


def test_allocate_and_release_ports(temp_git_repo: Path, tmp_path: Path):
    allocator = PortAllocator(repo_root=temp_git_repo)
    wt1 = tmp_path / "wt1"
    wt2 = tmp_path / "wt2"

    detected = {"PORT": 3000, "API_PORT": 8000}

    # Allocate for wt1
    alloc1 = allocator.allocate_ports(
        worktree_path=wt1,
        branch="feature/wt1",
        detected_ports=detected,
    )

    port_map1 = {a.port_variable: a.allocated_port for a in alloc1}
    assert port_map1["PORT"] >= 3001
    assert port_map1["API_PORT"] >= 8001

    # Allocate for wt2
    alloc2 = allocator.allocate_ports(
        worktree_path=wt2,
        branch="feature/wt2",
        detected_ports=detected,
    )

    port_map2 = {a.port_variable: a.allocated_port for a in alloc2}
    assert port_map2["PORT"] != port_map1["PORT"]
    assert port_map2["API_PORT"] != port_map1["API_PORT"]

    # Verify registry persisted
    assert allocator.registry_path.is_file()

    # Release wt1
    released = allocator.release_ports_for_path(wt1)
    assert len(released) == 2

    # Verify wt2 remains
    remaining = allocator.get_allocations_for_path(wt2)
    assert len(remaining) == 2
