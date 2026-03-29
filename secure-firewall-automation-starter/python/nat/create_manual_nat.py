from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.config import load_settings
from common.fmc_client import FMCClient
from common.logger import get_logger
from common.utils import write_csv

logger = get_logger(__name__)


def map_by_name(client: FMCClient, path: str) -> dict[str, dict[str, Any]]:
    data = client.get(path, params={"limit": 1000})
    return {item["name"]: item for item in data.get("items", [])}


def main() -> None:
    settings = load_settings()
    if not settings.nat_policy_id:
        raise SystemExit("Set NAT_POLICY_ID in python/.env before running create_manual_nat.py")

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "nat.csv"
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    hosts = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    networks = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")
    objects = {**hosts, **networks}
    endpoint = f"/api/fmc_config/v1/domain/{domain_uuid}/policy/ftdnatpolicies/{settings.nat_policy_id}/manualnatrules"

    results: list[dict[str, str]] = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        nat_type = str(row["nat_type"]).strip().upper()
        source = objects[str(row["source_network"]).strip()]
        translated = objects[str(row["translated_network"]).strip()]
        dest_if = str(row["destination_interface"]).strip()

        payload = {
            "type": "FTDManualNatRule",
            "name": name,
            "natType": nat_type,
            "enabled": True,
            "sourceInterface": {"name": "any", "id": "any", "type": "Interface"},
            "destinationInterface": {"name": dest_if, "id": dest_if, "type": "Interface"},
            "originalSource": {"id": source["id"], "name": source["name"], "type": source["type"]},
            "translatedSource": {"id": translated["id"], "name": translated["name"], "type": translated["type"]},
        }
        try:
            client.post(endpoint, payload)
            results.append({"name": name, "status": "CREATED", "detail": f"{nat_type} NAT rule created"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed creating NAT rule %s", name)
            results.append({"name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/nat_result.csv", results)
    logger.info("NAT creation complete: %s", out)
    logger.info("Manual NAT payloads vary by release. Confirm the exact payload in API Explorer for your FMC version.")


if __name__ == "__main__":
    main()
