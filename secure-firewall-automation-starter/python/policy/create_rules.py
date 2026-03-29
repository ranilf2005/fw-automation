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


def split_names(value: str) -> list[str]:
    return [v.strip() for v in str(value).split(";") if v.strip()]


def map_by_name(client: FMCClient, path: str) -> dict[str, dict[str, Any]]:
    data = client.get(path, params={"limit": 1000})
    return {item["name"]: item for item in data.get("items", [])}


def yes_no(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def ref(obj: dict[str, Any]) -> dict[str, str]:
    return {"id": obj["id"], "name": obj["name"], "type": obj["type"]}


def main() -> None:
    settings = load_settings()
    if not settings.access_policy_id:
        raise SystemExit("Set ACCESS_POLICY_ID in python/.env before running create_rules.py")

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "rules.csv"
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    zones = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/securityzones")
    hosts = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    networks = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")
    services = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/protocolportobjects")
    existing_rules = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/policy/accesspolicies/{settings.access_policy_id}/accessrules")
    objects = {**hosts, **networks}

    results: list[dict[str, str]] = []
    endpoint = f"/api/fmc_config/v1/domain/{domain_uuid}/policy/accesspolicies/{settings.access_policy_id}/accessrules"

    for _, row in df.iterrows():
        name = str(row["rule_name"]).strip()
        if name in existing_rules:
            results.append({"rule_name": name, "status": "SKIP", "detail": "Rule already exists by name"})
            continue
        try:
            payload = {
                "name": name,
                "type": "AccessRule",
                "action": str(row["action"]).strip().upper(),
                "enabled": yes_no(row["enabled"]),
                "logBegin": yes_no(row["log_begin"]),
                "logEnd": yes_no(row["log_end"]),
                "sendEventsToFMC": True,
                "newComments": [str(row["comment"]).strip()],
                "sourceZones": {"objects": [ref(zones[z]) for z in split_names(row["src_zones"])]},
                "destinationZones": {"objects": [ref(zones[z]) for z in split_names(row["dst_zones"])]},
                "sourceNetworks": {"objects": [ref(objects[n]) for n in split_names(row["src_networks"])]},
                "destinationNetworks": {"objects": [ref(objects[n]) for n in split_names(row["dst_networks"])]},
                "destinationPorts": {"objects": [ref(services[s]) for s in split_names(row["service_objects"])]},
            }
            client.post(endpoint, payload)
            results.append({"rule_name": name, "status": "CREATED", "detail": "Access rule created"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed creating rule %s", name)
            results.append({"rule_name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/rules_result.csv", results)
    logger.info("Rule creation complete: %s", out)
    logger.info("If your environment requires explicit deployment, deploy the policy from FMC or add a version-specific deploy workflow.")


if __name__ == "__main__":
    main()
