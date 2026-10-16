"""Patches and generates .env.local files in worktrees with allocated ports."""

from pathlib import Path
import re
from typing import Dict, List, Tuple


HEADER_COMMENT = "# WorktreeForge Managed Ports"


class EnvPatcher:
    """Updates or creates environment files with allocated port offsets."""

    def __init__(self, output_filename: str = ".env.local"):
        self.output_filename = output_filename

    def patch_worktree(
        self,
        worktree_path: Path,
        branch: str,
        ports: Dict[str, int],
    ) -> Path:
        """Write or update the env file in the target worktree."""
        target_file = worktree_path / self.output_filename
        existing_lines: List[str] = []

        if target_file.is_file():
            try:
                existing_lines = target_file.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except Exception:
                existing_lines = []

        new_lines, remaining_ports = self._update_existing_lines(
            existing_lines, ports
        )

        # Append remaining ports
        if remaining_ports:
            if new_lines and new_lines[-1].strip():
                new_lines.append("")
            new_lines.append(f"{HEADER_COMMENT} (branch: {branch})")
            for var_name, port_val in remaining_ports.items():
                new_lines.append(f"{var_name}={port_val}")

        # Write out
        output_content = "\n".join(new_lines) + "\n"
        target_file.write_text(output_content, encoding="utf-8")
        return target_file

    def _update_existing_lines(
        self, lines: List[str], ports: Dict[str, int]
    ) -> Tuple[List[str], Dict[str, int]]:
        """Update existing lines in place, returning remaining unwritten ports."""
        updated: List[str] = []
        remaining = dict(ports)

        for line in lines:
            trimmed = line.strip()
            matched = False

            for var_name, port_val in list(remaining.items()):
                pattern = rf"^(?:export\s+)?{re.escape(var_name)}\s*="
                if re.match(pattern, trimmed):
                    updated.append(f"{var_name}={port_val}")
                    del remaining[var_name]
                    matched = True
                    break

            if not matched:
                updated.append(line)

        return updated, remaining
