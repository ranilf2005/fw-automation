from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.fmc_client import FMCClient
from common.logger import get_logger
from common.utils import write_csv

logger = get_logger(__name__)


def get_existing(client: FMCClient, endpoint: str) -> dict[str, dict]:
    data = client.get(endpoint, params={"limit": 1000})
    return {item["name"]: item for item in data.get("items", [])}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "objects.csv"
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    existing_hosts = get_existing(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    existing_networks = get_existing(client, f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")

    results: list[dict[str, str]] = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        obj_type = str(row["type"]).strip()
        value = str(row["value"]).strip()
        description = str(row.get("description", "")).strip()

        if obj_type == "Host":
            existing = existing_hosts
            endpoint = f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts"
            payload = {"name": name, "type": "Host", "value": value, "description": description}
        else:
            existing = existing_networks
            endpoint = f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks"
            payload = {"name": name, "type": "Network", "value": value, "description": description}

        if name in existing:
            results.append({"name": name, "status": "SKIP", "detail": "Object already exists by name"})
            continue

        try:
            client.post(endpoint, payload)
            results.append({"name": name, "status": "CREATED", "detail": value})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed creating object %s", name)
            results.append({"name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/objects_result.csv", results)
    logger.info("Object creation complete: %s", out)


if __name__ == "__main__":
    main()
