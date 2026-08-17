# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Workspace allowlist and configuration.

An agent can only address Terraform directories that the operator listed. Names are
resolved against that list and the resulting path is re-verified before any command
runs, so traversal and symlink escapes fail closed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVER_ROOT = Path(__file__).resolve().parents[1]

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}


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


def _load_dotenv() -> None:
    env_file = SERVER_ROOT / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


@dataclass(frozen=True)
class Workspace:
    """One allowlisted Terraform directory."""

    name: str
    path: Path

    @property
    def initialised(self) -> bool:
        return (self.path / ".terraform").is_dir()

    def public(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "initialised": self.initialised,
            "config_files": sorted(p.name for p in self.path.glob("*.tf")),
        }


def discover_workspaces() -> dict[str, Workspace]:
    """Build the workspace allowlist.

    ``TF_MCP_WORKSPACES`` is a comma-separated list of ``name=path`` pairs, or bare
    paths whose directory name becomes the workspace name. When unset, the starter
    repository's ``terraform/`` directory is used.
    """
    _load_dotenv()
    raw = (os.getenv("TF_MCP_WORKSPACES") or "").strip()

    entries: list[tuple[str, Path]] = []
    if raw:
        for chunk in raw.split(","):
            item = chunk.strip()
            if not item:
                continue
            name, _, location = item.partition("=")
            if location:
                entries.append((name.strip(), Path(location.strip()).expanduser()))
            else:
                path = Path(name).expanduser()
                entries.append((path.name, path))
    else:
        entries.append(("starter", SERVER_ROOT.parents[1] / "terraform"))

    workspaces: dict[str, Workspace] = {}
    for name, path in entries:
        resolved = path.resolve()
        if not resolved.is_dir():
            raise ConfigError(f"Workspace {name!r} is not a directory: {resolved}")
        if not any(resolved.glob("*.tf")):
            raise ConfigError(f"Workspace {name!r} contains no .tf files: {resolved}")
        workspaces[name] = Workspace(name=name, path=resolved)

    if not workspaces:
        raise ConfigError("No Terraform workspaces configured. Set TF_MCP_WORKSPACES.")
    return workspaces


def resolve_workspace(name: str | None) -> Workspace:
    """Look up an allowlisted workspace by name.

    This is the choke point: only names present in the allowlist are accepted, so a
    caller can never point the server at an arbitrary directory.
    """
    workspaces = discover_workspaces()
    if not name:
        if len(workspaces) == 1:
            return next(iter(workspaces.values()))
        raise ConfigError(
            f"Several workspaces are configured {sorted(workspaces)}; pass workspace."
        )

    key = name.strip()
    if key not in workspaces:
        raise ConfigError(f"Unknown workspace {name!r}. Allowed workspaces: {sorted(workspaces)}")

    workspace = workspaces[key]
    if not workspace.path.is_dir():
        raise ConfigError(f"Workspace directory disappeared: {workspace.path}")
    return workspace


def apply_enabled() -> bool:
    """Whether ``terraform apply`` is permitted. Off unless explicitly enabled."""
    _load_dotenv()
    return as_bool(os.getenv("TF_MCP_ALLOW_APPLY"), default=False)


def timeout_seconds() -> int:
    _load_dotenv()
    raw = os.getenv("TF_MCP_TIMEOUT", "900")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"TF_MCP_TIMEOUT must be an integer, got {raw!r}") from exc
    if not 10 <= value <= 3600:
        raise ConfigError("TF_MCP_TIMEOUT must be between 10 and 3600 seconds.")
    return value
