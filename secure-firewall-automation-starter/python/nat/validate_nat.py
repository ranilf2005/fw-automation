from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.fmc_client import FMCClient

VALID_NAT_TYPES = {"STATIC", "DYNAMIC"}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "nat.csv"
    df = pd.read_csv(input_path)
    required = ["name", "nat_type", "source_network", "translated_network", "destination_interface"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise SystemExit(f"Missing required columns: {missing_cols}")

    client = FMCClient()
    domain_uuid = client.domain_uuid()
    hosts = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts", params={"limit": 1000})
    nets = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks", params={"limit": 1000})
    objects = {item["name"] for item in hosts.get("items", [])} | {item["name"] for item in nets.get("items", [])}

    errors: list[str] = []
    for idx, row in df.iterrows():
        nat_type = str(row["nat_type"]).strip().upper()
        if nat_type not in VALID_NAT_TYPES:
            errors.append(f"Row {idx + 2}: invalid nat_type {nat_type}")
        for obj_name in [str(row["source_network"]).strip(), str(row["translated_network"]).strip()]:
            if obj_name not in objects:
                errors.append(f"Row {idx + 2}: unknown network object {obj_name}")
        if not str(row["destination_interface"]).strip():
            errors.append(f"Row {idx + 2}: destination_interface is empty")

    if errors:
        print("Validation FAILED")
        for item in errors:
            print(f"- {item}")
        raise SystemExit(1)
    print("Validation PASSED")


if __name__ == "__main__":
    main()
