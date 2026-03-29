from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any
import pandas as pd
from .config import ROOT


def ensure_dirs() -> None:
    for rel in ["outputs/backups", "outputs/logs", "outputs/reports"]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def write_json(rel_path: str, data: Any) -> Path:
    ensure_dirs()
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


def write_csv(rel_path: str, rows: list[dict[str, Any]]) -> Path:
    ensure_dirs()
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def validate_ip_or_network(value: str) -> bool:
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
        else:
            ipaddress.ip_address(value)
        return True
    except ValueError:
        return False
