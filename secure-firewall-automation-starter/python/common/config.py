from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "python" / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass
class Settings:
    fmc_host: str
    username: str
    password: str
    verify_ssl: bool
    domain_uuid: str | None
    access_policy_id: str | None
    nat_policy_id: str | None
    root: Path = ROOT


def load_settings() -> Settings:
    return Settings(
        fmc_host=os.getenv("FMC_HOST", "").rstrip("/"),
        username=os.getenv("FMC_USERNAME", ""),
        password=os.getenv("FMC_PASSWORD", ""),
        verify_ssl=as_bool(os.getenv("VERIFY_SSL"), default=False),
        domain_uuid=os.getenv("FMC_DOMAIN_UUID") or None,
        access_policy_id=os.getenv("ACCESS_POLICY_ID") or None,
        nat_policy_id=os.getenv("NAT_POLICY_ID") or None,
    )
