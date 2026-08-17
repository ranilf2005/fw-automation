# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Create FMC protocol/port service objects from a CSV file."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.cli import parse_csv_args  # noqa: E402
from common.fmc_client import FMCClient  # noqa: E402
from common.logger import get_logger  # noqa: E402
from common.utils import write_csv  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    input_path = parse_csv_args(
        "Create FMC protocol/port service objects from a CSV file.", "inputs/services.csv"
    ).input
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    # Confirm this path and the payload fields in https://<fmc-host>/api/api-explorer first.
    endpoint = f"/api/fmc_config/v1/domain/{domain_uuid}/object/protocolportobjects"
    existing_by_name = {item["name"]: item for item in client.get_all(endpoint)}

    results: list[dict[str, str]] = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        protocol = str(row["protocol"]).strip().upper()
        port = str(row["port"]).strip()
        description = str(row.get("description", "")).strip()
        if name in existing_by_name:
            results.append(
                {"name": name, "status": "SKIP", "detail": "Service already exists by name"}
            )
            continue
        payload = {
            "name": name,
            "type": "ProtocolPortObject",
            "protocol": protocol,
            "port": port,
            "description": description,
        }
        try:
            client.post(endpoint, payload)
            results.append({"name": name, "status": "CREATED", "detail": f"{protocol}/{port}"})
        except (requests.RequestException, ValueError) as exc:
            logger.error("Failed creating service %s: %s", name, exc)
            results.append({"name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/services_result.csv", results)
    logger.info("Service creation complete: %s", out)


if __name__ == "__main__":
    main()
