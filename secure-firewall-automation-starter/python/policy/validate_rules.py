from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.fmc_client import FMCClient

REQUIRED_COLUMNS = [
    "rule_name",
    "src_zones",
    "dst_zones",
    "src_networks",
    "dst_networks",
    "service_objects",
    "action",
    "enabled",
    "log_begin",
    "log_end",
    "comment",
]
VALID_ACTIONS = {"ALLOW", "BLOCK", "TRUST", "MONITOR"}


def get_names(client: FMCClient, path: str) -> set[str]:
    data = client.get(path, params={"limit": 1000})
    return {item["name"] for item in data.get("items", [])}


def split_names(value: str) -> list[str]:
    return [v.strip() for v in str(value).split(";") if v.strip()]


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "rules.csv"
    df = pd.read_csv(input_path)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise SystemExit(f"Missing required columns: {missing_cols}")

    client = FMCClient()
    domain_uuid = client.domain_uuid()
    zones = get_names(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/securityzones")
    hosts = get_names(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    networks = get_names(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")
    service_objects = get_names(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/protocolportobjects")
    network_names = hosts | networks

    errors: list[str] = []
    for idx, row in df.iterrows():
        action = str(row["action"]).strip().upper()
        if action not in VALID_ACTIONS:
            errors.append(f"Row {idx + 2}: invalid action {action}")
        for zone in split_names(row["src_zones"]) + split_names(row["dst_zones"]):
            if zone not in zones:
                errors.append(f"Row {idx + 2}: unknown zone {zone}")
        for net in split_names(row["src_networks"]) + split_names(row["dst_networks"]):
            if net not in network_names:
                errors.append(f"Row {idx + 2}: unknown network object {net}")
        for svc in split_names(row["service_objects"]):
            if svc not in service_objects:
                errors.append(f"Row {idx + 2}: unknown service object {svc}")

    if errors:
        print("Validation FAILED")
        for item in errors:
            print(f"- {item}")
        raise SystemExit(1)
    print("Validation PASSED")


if __name__ == "__main__":
    main()
