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


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "inputs" / "services.csv"
    df = pd.read_csv(input_path)
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    endpoint = f"/api/fmc_config/v1/domain/{domain_uuid}/object/protocolportobjects"
    existing = client.get(endpoint, params={"limit": 1000})
    existing_by_name = {item["name"]: item for item in existing.get("items", [])}

    results: list[dict[str, str]] = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        protocol = str(row["protocol"]).strip().upper()
        port = str(row["port"]).strip()
        description = str(row.get("description", "")).strip()
        if name in existing_by_name:
            results.append({"name": name, "status": "SKIP", "detail": "Service already exists by name"})
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed creating service %s", name)
            results.append({"name": name, "status": "FAILED", "detail": str(exc)})

    out = write_csv("outputs/reports/services_result.csv", results)
    logger.info("Service creation complete: %s", out)


if __name__ == "__main__":
    main()
