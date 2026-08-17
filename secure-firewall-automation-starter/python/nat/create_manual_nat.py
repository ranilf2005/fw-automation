# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Create FTD manual NAT rules in an FMC NAT policy from a CSV file."""

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


def map_by_name(client: FMCClient, path: str) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in client.get_all(path)}


def main() -> None:
    settings = load_settings()
    if not settings.nat_policy_id:
        raise SystemExit("Set NAT_POLICY_ID in python/.env before running create_manual_nat.py")

    input_path = parse_csv_args(
        "Create FTD manual NAT rules in an FMC NAT policy from a CSV file.", "inputs/nat.csv"
    ).input
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    hosts = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    networks = map_by_name(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")
    objects = {**hosts, **networks}
    endpoint = (
        f"/api/fmc_config/v1/domain/{domain_uuid}"
        f"/policy/ftdnatpolicies/{settings.nat_policy_id}/manualnatrules"
    )

    results: list[dict[str, str]] = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        nat_type = str(row["nat_type"]).strip().upper()
        source_name = str(row["source_network"]).strip()
        translated_name = str(row["translated_network"]).strip()
        dest_if = str(row["destination_interface"]).strip()

        missing = [n for n in (source_name, translated_name) if n not in objects]
        if missing:
            detail = f"Unknown network/host object(s) in FMC: {', '.join(missing)}"
            logger.error("Skipping NAT rule %s - %s", name, detail)
            results.append({"name": name, "status": "SKIP", "detail": detail})
            continue

        source = objects[source_name]
        translated = objects[translated_name]

        payload = {
            "type": "FTDManualNatRule",
            "name": name,
            "natType": nat_type,
            "enabled": True,
            "sourceInterface": {"name": "any", "id": "any", "type": "Interface"},
            "destinationInterface": {"name": dest_if, "id": dest_if, "type": "Interface"},
            "originalSource": {"id": source["id"], "name": source["name"], "type": source["type"]},
            "translatedSource": {
                "id": translated["id"],
                "name": translated["name"],
                "type": translated["type"],
            },
        }
        try:
            client.post(endpoint, payload)
            results.append(
                {"name": name, "status": "CREATED", "detail": f"{nat_type} NAT rule created"}
            )
        except (requests.RequestException, ValueError) as exc:
            logger.error("Failed creating NAT rule %s: %s", name, exc)
            results.append({"name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/nat_result.csv", results)
    logger.info("NAT creation complete: %s", out)
    logger.info(
        "Manual NAT payloads vary by release. "
        "Confirm the exact payload in API Explorer for your FMC version."
    )


if __name__ == "__main__":
    main()
