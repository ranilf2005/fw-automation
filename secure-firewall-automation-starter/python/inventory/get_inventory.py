from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.fmc_client import FMCClient
from common.logger import get_logger
from common.utils import write_json

logger = get_logger(__name__)


def main() -> None:
    client = FMCClient()
    domains = client.get("/api/fmc_platform/v1/info/domain")
    write_json("outputs/reports/domains.json", domains)

    domain_uuid = client.domain_uuid()
    devices = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/devices/devicerecords", params={"limit": 1000})
    write_json("outputs/reports/devices.json", devices)

    networks = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks", params={"limit": 1000})
    write_json("outputs/reports/network_objects.json", networks)

    hosts = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts", params={"limit": 1000})
    write_json("outputs/reports/host_objects.json", hosts)

    zones = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/securityzones", params={"limit": 1000})
    write_json("outputs/reports/security_zones.json", zones)

    policies = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/policy/accesspolicies", params={"limit": 1000})
    write_json("outputs/reports/access_policies.json", policies)

    logger.info("Inventory export complete. Files written to outputs/reports")


if __name__ == "__main__":
    main()
