"""Configuration loader and manager for WorktreeForge."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from worktreeforge.core.models import AppConfig


CONFIG_FILENAMES = [
    ".worktreeforge.yaml",
    ".worktreeforge.yml",
    "worktreeforge.yaml",
]


def _deep_update(source: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update a dictionary."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            source[key] = _deep_update(source[key], value)
        else:
            source[key] = value
    return source


def get_global_config_path() -> Path:
    """Return standard location for global config."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    return base / "worktreeforge" / "config.yaml"


def find_repo_config_path(repo_root: Optional[Path]) -> Optional[Path]:
    """Find configuration file in repository root if present."""
    if not repo_root or not repo_root.is_dir():
        return None
    for name in CONFIG_FILENAMES:
        candidate = repo_root / name
        if candidate.is_file():
            return candidate
    return None


def load_config(repo_root: Optional[Path] = None) -> AppConfig:
    """Load merged configuration from defaults, global, and repo levels."""
    data: Dict[str, Any] = AppConfig().model_dump()

    # 1. Global config
    global_path = get_global_config_path()
    if global_path.is_file():
        try:
            with open(global_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    data = _deep_update(data, content)
        except Exception:
            pass

    # 2. Repo config
    repo_cfg_path = find_repo_config_path(repo_root)
    if repo_cfg_path and repo_cfg_path.is_file():
        try:
            with open(repo_cfg_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    data = _deep_update(data, content)
        except Exception:
            pass

    return AppConfig.model_validate(data)


def save_repo_config(repo_root: Path, config: AppConfig) -> Path:
    """Save configuration to repository root."""
    target = repo_root / ".worktreeforge.yaml"
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f, sort_keys=False)
    return target
