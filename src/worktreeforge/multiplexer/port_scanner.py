"""Scans repository files for declared port numbers and environment variables."""

import json
from pathlib import Path
import re
from typing import Dict, List, Optional
import yaml

from worktreeforge.core.models import PortMultiplexerConfig


PORT_ENV_PATTERN = re.compile(
    r"^(?:export\s+)?([A-Z0-9_]*PORT[A-Z0-9_]*)\s*=\s*['\"]?([0-9]{2,5})['\"]?",
    re.MULTILINE,
)

PACKAGE_JSON_SCRIPT_PORT_PATTERN = re.compile(
    r"(?:-p|--port|PORT=)\s*['\"]?([0-9]{2,5})['\"]?"
)


class PortScanner:
    """Scans repository directory to find default configured port numbers."""

    def __init__(self, config: Optional[PortMultiplexerConfig] = None):
        self.config = config or PortMultiplexerConfig()

    def scan_directory(self, root: Path) -> Dict[str, int]:
        """Scan directory and return a dictionary of port variable names and base port numbers."""
        found_ports: Dict[str, int] = {}

        # 1. Scan configured env files
        for env_filename in self.config.scan_env_files:
            candidate = root / env_filename
            if candidate.is_file():
                ports_from_env = self._scan_env_file(candidate)
                for var_name, port_num in ports_from_env.items():
                    if var_name not in found_ports:
                        found_ports[var_name] = port_num

        # 2. Scan package.json if enabled and PORT not yet found
        if self.config.scan_package_json:
            pkg_json = root / "package.json"
            if pkg_json.is_file():
                pkg_ports = self._scan_package_json(pkg_json)
                for var_name, port_num in pkg_ports.items():
                    if var_name not in found_ports:
                        found_ports[var_name] = port_num

        # 3. Scan docker-compose files
        for dc_name in ["docker-compose.yml", "docker-compose.yaml", "compose.yaml"]:
            dc_path = root / dc_name
            if dc_path.is_file():
                dc_ports = self._scan_docker_compose(dc_path)
                for var_name, port_num in dc_ports.items():
                    if var_name not in found_ports:
                        found_ports[var_name] = port_num

        # Fallback to standard PORT=3000 if nothing detected
        if not found_ports:
            found_ports["PORT"] = 3000

        return found_ports

    def _scan_env_file(self, file_path: Path) -> Dict[str, int]:
        """Parse env file looking for PORT-like variables."""
        ports: Dict[str, int] = {}
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            matches = PORT_ENV_PATTERN.findall(content)
            for var_name, port_str in matches:
                try:
                    port = int(port_str)
                    if 1024 <= port <= 65535:
                        ports[var_name] = port
                except ValueError:
                    continue
        except Exception:
            pass
        return ports

    def _scan_package_json(self, file_path: Path) -> Dict[str, int]:
        """Extract declared ports from npm/yarn/pnpm scripts."""
        ports: Dict[str, int] = {}
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(content)
            scripts = data.get("scripts", {})
            for script_name, cmd in scripts.items():
                if isinstance(cmd, str):
                    matches = PACKAGE_JSON_SCRIPT_PORT_PATTERN.findall(cmd)
                    for port_str in matches:
                        try:
                            port = int(port_str)
                            if 1024 <= port <= 65535:
                                # Prioritize dev/start script ports
                                var_name = "PORT"
                                if "vite" in cmd:
                                    var_name = "VITE_PORT"
                                ports[var_name] = port
                                return ports
                        except ValueError:
                            continue
        except Exception:
            pass
        return ports

    def _scan_docker_compose(self, file_path: Path) -> Dict[str, int]:
        """Extract exposed host ports from docker compose services."""
        ports: Dict[str, int] = {}
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                return ports
            services = data.get("services", {})
            if isinstance(services, dict):
                for s_name, s_def in services.items():
                    if isinstance(s_def, dict) and "ports" in s_def:
                        port_list = s_def["ports"]
                        if isinstance(port_list, list):
                            for p_entry in port_list:
                                if isinstance(p_entry, str) and ":" in p_entry:
                                    host_port = p_entry.split(":")[0].strip()
                                    if host_port.isdigit():
                                        port = int(host_port)
                                        if 1024 <= port <= 65535:
                                            ports[f"{s_name.upper()}_PORT"] = port
        except Exception:
            pass
        return ports
