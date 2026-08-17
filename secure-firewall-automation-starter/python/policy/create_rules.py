# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Create FMC access control rules from a CSV file."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.cli import parse_csv_args  # noqa: E402
from common.config import load_settings  # noqa: E402
from common.fmc_client import FMCClient  # noqa: E402
from common.logger import get_logger  # noqa: E402
from common.utils import write_csv  # noqa: E402

logger = get_logger(__name__)


class MissingObjectError(LookupError):
    """A CSV row referenced an object name that does not exist in FMC."""


def split_names(value: str) -> list[str]:
    return [v.strip() for v in str(value).split(";") if v.strip()]


def map_by_name(client: FMCClient, path: str) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in client.get_all(path)}


def yes_no(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def ref(obj: dict[str, Any]) -> dict[str, str]:
    return {"id": obj["id"], "name": obj["name"], "type": obj["type"]}


def refs(catalogue: dict[str, dict[str, Any]], names: list[str], kind: str) -> list[dict[str, str]]:
    """Resolve names to FMC object references, naming anything that is missing."""
    missing = [n for n in names if n not in catalogue]
    if missing:
        raise MissingObjectError(f"unknown {kind}: {', '.join(missing)}")
    return [ref(catalogue[n]) for n in names]


def main() -> None:
    settings = load_settings()
    if not settings.access_policy_id:
        raise SystemExit("Set ACCESS_POLICY_ID in python/.env before running create_rules.py")

    input_path = parse_csv_args(
        "Create FMC access control rules from a CSV file.", "inputs/rules.csv"
    ).input
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    zones = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/securityzones")
    hosts = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    networks = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")
    services = map_by_name(
        client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/protocolportobjects"
    )
    endpoint = (
        f"/api/fmc_config/v1/domain/{domain_uuid}"
        f"/policy/accesspolicies/{settings.access_policy_id}/accessrules"
    )
    existing_rules = map_by_name(client, endpoint)
    objects = {**hosts, **networks}

    results: list[dict[str, str]] = []

    for _, row in df.iterrows():
        name = str(row["rule_name"]).strip()
        if name in existing_rules:
            results.append(
                {"rule_name": name, "status": "SKIP", "detail": "Rule already exists by name"}
            )
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
                "sourceZones": {
                    "objects": refs(zones, split_names(row["src_zones"]), "security zone")
                },
                "destinationZones": {
                    "objects": refs(zones, split_names(row["dst_zones"]), "security zone")
                },
                "sourceNetworks": {
                    "objects": refs(objects, split_names(row["src_networks"]), "network object")
                },
                "destinationNetworks": {
                    "objects": refs(objects, split_names(row["dst_networks"]), "network object")
                },
                "destinationPorts": {
                    "objects": refs(services, split_names(row["service_objects"]), "service object")
                },
            }
            client.post(endpoint, payload)
            results.append(
                {"rule_name": name, "status": "CREATED", "detail": "Access rule created"}
            )
        except MissingObjectError as exc:
            logger.error("Skipping rule %s - %s", name, exc)
            results.append({"rule_name": name, "status": "SKIP", "detail": str(exc)})
        except (requests.RequestException, ValueError) as exc:
            logger.error("Failed creating rule %s: %s", name, exc)
            results.append({"rule_name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/rules_result.csv", results)
    logger.info("Rule creation complete: %s", out)
    logger.info(
        "If your environment requires explicit deployment, deploy the policy from FMC "
        "or add a version-specific deploy workflow."
    )


if __name__ == "__main__":
    main()
