from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

VALID_PROTOCOLS = {"TCP", "UDP"}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "services.csv"
    df = pd.read_csv(input_path)
    required = ["name", "protocol", "port", "description"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise SystemExit(f"Missing required columns: {missing_cols}")

    errors: list[str] = []
    seen: set[str] = set()
    for idx, row in df.iterrows():
        name = str(row["name"]).strip()
        protocol = str(row["protocol"]).strip().upper()
        port = str(row["port"]).strip()
        if name in seen:
            errors.append(f"Row {idx + 2}: duplicate service name {name}")
        seen.add(name)
        if protocol not in VALID_PROTOCOLS:
            errors.append(f"Row {idx + 2}: invalid protocol {protocol}")
        try:
            port_int = int(port)
            if not (1 <= port_int <= 65535):
                errors.append(f"Row {idx + 2}: port out of range {port}")
        except ValueError:
            errors.append(f"Row {idx + 2}: invalid port {port}")

    if errors:
        print("Validation FAILED")
        for item in errors:
            print(f"- {item}")
        raise SystemExit(1)
    print("Validation PASSED")


if __name__ == "__main__":
    main()
