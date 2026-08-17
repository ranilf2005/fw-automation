# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Profile-based configuration for one or many FMC instances.

Two modes are supported:

* **env mode** - a single FMC described by ``FMC_BASE_URL`` / ``FMC_USERNAME`` /
  ``FMC_PASSWORD`` in the environment or a root ``.env``.
* **profile mode** - one ``*.env`` file per FMC in ``FMC_PROFILES_DIR``. Enabled
  automatically when that variable is set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[1]

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}

# Hard cap so a single tool call can never pull an unbounded object list into the
# model context.
MAX_PAGE_SIZE = 1000
MAX_RESULTS = 5000


class ConfigError(ValueError):
    """Raised when the server is misconfigured."""


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
class FMCProfile:
    """One addressable FMC instance."""

    id: str
    base_url: str
    username: str
    password: str = field(repr=False)
    display_name: str = ""
    aliases: tuple[str, ...] = ()
    verify_ssl: bool = True
    ca_bundle: str | None = None
    domain_uuid: str | None = None

    @property
    def verify(self) -> bool | str:
        """Value handed to httpx for TLS verification."""
        return self.ca_bundle or self.verify_ssl

    def public(self) -> dict[str, object]:
        """Serialisable view with no secret material."""
        return {
            "id": self.id,
            "display_name": self.display_name or self.id,
            "aliases": list(self.aliases),
            "base_url": self.base_url,
            "username": self.username,
            "tls_verification": bool(self.verify),
            "domain_uuid": self.domain_uuid,
        }


def _profile_from_mapping(values: dict[str, str | None], fallback_id: str) -> FMCProfile:
    def get(key: str) -> str | None:
        raw = values.get(key)
        return raw.strip() if isinstance(raw, str) and raw.strip() else None

    base_url = (get("FMC_BASE_URL") or "").rstrip("/")
    if not base_url:
        raise ConfigError(f"Profile {fallback_id!r} is missing FMC_BASE_URL.")
    if not base_url.startswith("https://"):
        raise ConfigError(
            f"Profile {fallback_id!r}: FMC_BASE_URL must use https://, got {base_url!r}. "
            "Sending API credentials over plaintext HTTP is not supported."
        )

    username = get("FMC_USERNAME")
    password = get("FMC_PASSWORD")
    if not username or not password:
        raise ConfigError(f"Profile {fallback_id!r} is missing FMC_USERNAME or FMC_PASSWORD.")

    ca_bundle = get("FMC_CA_BUNDLE")
    if ca_bundle and not Path(ca_bundle).is_file():
        raise ConfigError(f"FMC_CA_BUNDLE does not exist: {ca_bundle}")

    aliases = tuple(
        a.strip().lower() for a in (get("FMC_PROFILE_ALIASES") or "").split(",") if a.strip()
    )

    return FMCProfile(
        id=(get("FMC_PROFILE_ID") or fallback_id).lower(),
        base_url=base_url,
        username=username,
        password=password,
        display_name=get("FMC_PROFILE_DISPLAY_NAME") or "",
        aliases=aliases,
        verify_ssl=as_bool(values.get("FMC_VERIFY_SSL"), default=True),
        ca_bundle=ca_bundle,
        domain_uuid=get("FMC_DOMAIN_UUID"),
    )


def load_profiles() -> dict[str, FMCProfile]:
    """Discover every configured FMC, keyed by profile id."""
    root_env = ROOT / ".env"
    if root_env.is_file():
        load_dotenv(root_env, override=False)

    profiles_dir = os.getenv("FMC_PROFILES_DIR")
    if not profiles_dir:
        return {"default": _profile_from_mapping(dict(os.environ), "default")}

    directory = Path(profiles_dir)
    if not directory.is_absolute():
        directory = ROOT / directory
    if not directory.is_dir():
        raise ConfigError(f"FMC_PROFILES_DIR is not a directory: {directory}")

    profiles: dict[str, FMCProfile] = {}
    for env_file in sorted(directory.glob("*.env")):
        if env_file.name.startswith("."):
            continue
        profile = _profile_from_mapping(dict(dotenv_values(env_file)), env_file.stem)
        if profile.id in profiles:
            raise ConfigError(f"Duplicate FMC_PROFILE_ID {profile.id!r} in {env_file}")
        profiles[profile.id] = profile

    if not profiles:
        raise ConfigError(f"No *.env profile files found in {directory}")
    return profiles


def resolve_profile(profiles: dict[str, FMCProfile], requested: str | None) -> FMCProfile:
    """Look a profile up by id or alias, falling back to the configured default."""
    if not profiles:
        raise ConfigError("No FMC profiles are configured.")

    if not requested:
        default_id = (os.getenv("FMC_PROFILE_DEFAULT") or "").lower()
        if default_id:
            if default_id not in profiles:
                raise ConfigError(
                    f"FMC_PROFILE_DEFAULT={default_id!r} does not match any profile: "
                    f"{sorted(profiles)}"
                )
            return profiles[default_id]
        if len(profiles) == 1:
            return next(iter(profiles.values()))
        raise ConfigError(
            f"Several FMC profiles are configured {sorted(profiles)}; pass fmc_profile "
            "or set FMC_PROFILE_DEFAULT."
        )

    key = requested.strip().lower()
    if key in profiles:
        return profiles[key]
    for profile in profiles.values():
        if key in profile.aliases:
            return profile
    raise ConfigError(f"Unknown FMC profile {requested!r}. Known profiles: {sorted(profiles)}")


def writes_enabled() -> bool:
    """Whether mutating tools are permitted. Off unless explicitly enabled."""
    return as_bool(os.getenv("FMC_ALLOW_WRITES"), default=False)
