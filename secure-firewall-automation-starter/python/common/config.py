# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Environment-backed configuration for the FMC automation scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "python" / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


def as_bool(value: str | None, default: bool = False) -> bool:
    """Parse a boolean from an environment string, falling back to ``default``."""
    if value is None:
        return default
    normalised = value.strip().lower()
    if not normalised:
        return default
    if normalised in _TRUE_VALUES:
        return True
    if normalised in _FALSE_VALUES:
        return False
    raise ValueError(
        f"Cannot interpret {value!r} as a boolean. "
        f"Use one of {sorted(_TRUE_VALUES | _FALSE_VALUES)}."
    )


@dataclass
class Settings:
    """Resolved runtime settings for a single FMC target."""

    fmc_host: str
    username: str
    password: str
    verify_ssl: bool
    ca_bundle: str | None
    domain_uuid: str | None
    access_policy_id: str | None
    nat_policy_id: str | None
    root: Path = ROOT

    @property
    def verify(self) -> bool | str:
        """Value handed to ``requests`` for TLS verification.

        A CA bundle path wins over the boolean flag, so a private CA can be trusted
        without switching verification off entirely.
        """
        if self.ca_bundle:
            return self.ca_bundle
        return self.verify_ssl


def load_settings() -> Settings:
    """Build :class:`Settings` from the environment and ``python/.env``.

    TLS verification defaults to **enabled**. Set ``VERIFY_SSL=false`` only against a
    lab FMC with a self-signed certificate, and prefer ``FMC_CA_BUNDLE`` instead.
    """
    ca_bundle = os.getenv("FMC_CA_BUNDLE") or None
    if ca_bundle and not Path(ca_bundle).is_file():
        raise ValueError(f"FMC_CA_BUNDLE points at a file that does not exist: {ca_bundle}")

    return Settings(
        fmc_host=os.getenv("FMC_HOST", "").rstrip("/"),
        username=os.getenv("FMC_USERNAME", ""),
        password=os.getenv("FMC_PASSWORD", ""),
        verify_ssl=as_bool(os.getenv("VERIFY_SSL"), default=True),
        ca_bundle=ca_bundle,
        domain_uuid=os.getenv("FMC_DOMAIN_UUID") or None,
        access_policy_id=os.getenv("ACCESS_POLICY_ID") or None,
        nat_policy_id=os.getenv("NAT_POLICY_ID") or None,
    )
