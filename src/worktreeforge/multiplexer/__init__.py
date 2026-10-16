"""Multiplexer package for dynamic port allocation and env patching."""

from worktreeforge.multiplexer.env_patcher import EnvPatcher
from worktreeforge.multiplexer.port_allocator import (
    PortAllocator,
    is_port_available,
)
from worktreeforge.multiplexer.port_scanner import PortScanner

__all__ = [
    "EnvPatcher",
    "PortAllocator",
    "PortScanner",
    "is_port_available",
]
