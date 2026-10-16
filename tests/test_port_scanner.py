"""Tests for repository port scanning."""

from pathlib import Path
from worktreeforge.multiplexer.port_scanner import PortScanner


def test_scan_env_file(temp_git_repo: Path):
    scanner = PortScanner()
    ports = scanner.scan_directory(temp_git_repo)

    assert "PORT" in ports
    assert ports["PORT"] == 3000
    assert "API_PORT" in ports
    assert ports["API_PORT"] == 8000


def test_scan_package_json(tmp_path: Path):
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text('{"scripts": {"dev": "vite --port 5173"}}\n', encoding="utf-8")

    scanner = PortScanner()
    ports = scanner.scan_directory(tmp_path)

    assert "VITE_PORT" in ports
    assert ports["VITE_PORT"] == 5173


def test_fallback_port(tmp_path: Path):
    scanner = PortScanner()
    ports = scanner.scan_directory(tmp_path)

    assert "PORT" in ports
    assert ports["PORT"] == 3000
