# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Configuration and the playbook allowlist.

The single most important security property of this server: an agent can never name an
arbitrary file. It picks from a resolved allowlist of playbooks that live inside a fixed
project directory, and every path is re-resolved and re-checked before execution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

SERVER_ROOT = Path(__file__).resolve().parents[1]

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}

# Playbooks that change FMC state. Everything else is treated as read-only.
MUTATING_PREFIXES = ("create_", "update_", "delete_", "deploy_", "remove_")


class ConfigError(ValueError):
    """Raised when the server is misconfigured or a path is out of bounds."""


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalised = value.strip().lower()
    if not normalised:
        return default
    if normalised in _TRUE:
        return True
    if normalised in _FALSE:
        return False
    raise ConfigError(f"Cannot interpret {value!r} as a boolean.")


@dataclass(frozen=True)
class Playbook:
    """One allowlisted playbook."""

    name: str
    path: Path
    description: str
    mutates: bool

    def public(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "mutates_configuration": self.mutates,
            "relative_path": self.name + ".yml",
        }


def _load_dotenv() -> None:
    env_file = SERVER_ROOT / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


def project_root() -> Path:
    """Directory holding ``ansible/``. Defaults to the starter repo two levels up."""
    _load_dotenv()
    configured = os.getenv("ANSIBLE_PROJECT_DIR")
    root = Path(configured).expanduser() if configured else SERVER_ROOT.parents[1]
    root = root.resolve()
    if not (root / "ansible").is_dir():
        raise ConfigError(
            f"No 'ansible' directory under {root}. Set ANSIBLE_PROJECT_DIR to the "
            "repository root that contains ansible/playbooks/."
        )
    return root


def playbook_dir() -> Path:
    return project_root() / "ansible" / "playbooks"


def inventory_path() -> Path:
    path = project_root() / "ansible" / "inventory.yml"
    if not path.is_file():
        raise ConfigError(f"Inventory not found: {path}")
    return path


def _describe(path: Path) -> str:
    """Pull the play name out of the YAML for a human-readable description."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return "(could not parse playbook)"
    if isinstance(loaded, list) and loaded and isinstance(loaded[0], dict):
        return str(loaded[0].get("name", path.stem))
    return path.stem


def discover_playbooks() -> dict[str, Playbook]:
    """Build the allowlist from the playbook directory."""
    directory = playbook_dir()
    if not directory.is_dir():
        raise ConfigError(f"Playbook directory not found: {directory}")

    allowed = {
        name.strip()
        for name in (os.getenv("ANSIBLE_PLAYBOOK_ALLOWLIST") or "").split(",")
        if name.strip()
    }

    playbooks: dict[str, Playbook] = {}
    for path in sorted(directory.glob("*.yml")):
        name = path.stem
        if allowed and name not in allowed:
            continue
        playbooks[name] = Playbook(
            name=name,
            path=path.resolve(),
            description=_describe(path),
            mutates=name.startswith(MUTATING_PREFIXES),
        )

    if not playbooks:
        raise ConfigError(f"No playbooks found in {directory}")
    return playbooks


def resolve_playbook(name: str) -> Playbook:
    """Look up an allowlisted playbook, rejecting anything outside the directory.

    This is the choke point. ``name`` is matched against the discovered allowlist by
    exact key, and the resulting path is re-verified to live under the playbook
    directory, so traversal attempts such as ``../../etc/passwd`` cannot resolve.
    """
    playbooks = discover_playbooks()
    key = name.strip()
    if key not in playbooks:
        raise ConfigError(f"Unknown playbook {name!r}. Allowed playbooks: {sorted(playbooks)}")

    playbook = playbooks[key]
    directory = playbook_dir().resolve()
    if not playbook.path.is_relative_to(directory):
        raise ConfigError(f"Playbook {name!r} resolved outside {directory}. Refusing.")
    if not playbook.path.is_file():
        raise ConfigError(f"Playbook file disappeared: {playbook.path}")
    return playbook


def run_enabled() -> bool:
    """Whether real (non ``--check``) playbook execution is permitted."""
    _load_dotenv()
    return as_bool(os.getenv("ANSIBLE_MCP_ALLOW_RUN"), default=False)


def timeout_seconds() -> int:
    _load_dotenv()
    raw = os.getenv("ANSIBLE_MCP_TIMEOUT", "600")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"ANSIBLE_MCP_TIMEOUT must be an integer, got {raw!r}") from exc
    if not 10 <= value <= 3600:
        raise ConfigError("ANSIBLE_MCP_TIMEOUT must be between 10 and 3600 seconds.")
    return value
