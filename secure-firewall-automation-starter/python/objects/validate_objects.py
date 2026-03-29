from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.utils import validate_ip_or_network

VALID_TYPES = {"Host", "Network"}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "objects.csv"
    df = pd.read_csv(input_path)
    required = ["name", "type", "value", "description"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise SystemExit(f"Missing required columns: {missing_cols}")

    errors: list[str] = []
    seen: set[str] = set()
    for idx, row in df.iterrows():
        name = str(row["name"]).strip()
        obj_type = str(row["type"]).strip()
        value = str(row["value"]).strip()
        if not name:
            errors.append(f"Row {idx + 2}: name is empty")
        if name in seen:
            errors.append(f"Row {idx + 2}: duplicate object name in CSV: {name}")
        seen.add(name)
        if obj_type not in VALID_TYPES:
            errors.append(f"Row {idx + 2}: invalid type {obj_type}; use Host or Network")
        if not validate_ip_or_network(value):
            errors.append(f"Row {idx + 2}: invalid IP or subnet value {value}")
        if obj_type == "Host" and "/" in value:
            errors.append(f"Row {idx + 2}: Host type cannot use subnet value {value}")
        if obj_type == "Network" and "/" not in value:
            errors.append(f"Row {idx + 2}: Network type should use CIDR subnet, got {value}")

    if errors:
        print("Validation FAILED")
        for item in errors:
            print(f"- {item}")
        raise SystemExit(1)
    print("Validation PASSED")


if __name__ == "__main__":
    main()
