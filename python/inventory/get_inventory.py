# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Read-only inventory export from FMC into outputs/reports/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.cli import parse_args  # noqa: E402
from common.fmc_client import FMCClient  # noqa: E402
from common.logger import get_logger  # noqa: E402
from common.utils import write_json  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    parse_args("Export a read-only inventory from FMC into outputs/reports/.")
    client = FMCClient()
    domains = client.get("/api/fmc_platform/v1/info/domain")
    write_json("outputs/reports/domains.json", domains)

    domain_uuid = client.domain_uuid()
    base = f"/api/fmc_config/v1/domain/{domain_uuid}"
    exports = {
        "devices.json": f"{base}/devices/devicerecords",
        "network_objects.json": f"{base}/object/networks",
        "host_objects.json": f"{base}/object/hosts",
        "security_zones.json": f"{base}/object/securityzones",
        "access_policies.json": f"{base}/policy/accesspolicies",
    }
    for filename, path in exports.items():
        write_json(f"outputs/reports/{filename}", {"items": client.get_all(path)})

    logger.info("Inventory export complete. Files written to outputs/reports")


if __name__ == "__main__":
    main()
