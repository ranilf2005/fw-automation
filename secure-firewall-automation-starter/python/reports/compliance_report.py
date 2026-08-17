# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Read-only compliance scan of FMC objects and access rules."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.cli import parse_args  # noqa: E402
from common.config import load_settings  # noqa: E402
from common.fmc_client import FMCClient  # noqa: E402
from common.logger import get_logger  # noqa: E402
from common.utils import write_csv  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    parse_args("Run a read-only compliance scan of FMC objects and access rules.")
    settings = load_settings()
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    findings: list[dict[str, str]] = []

    hosts = client.get_all(f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts")
    networks = client.get_all(f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks")

    # duplicate value checks
    value_seen: dict[str, str] = {}
    for item in hosts + networks:
        value = item.get("value", "")
        name = item.get("name", "")
        if not name.startswith(("APP_", "NET_", "HOST_", "APP", "DB", "DNS")):
            findings.append(
                {
                    "type": "NAMING",
                    "name": name,
                    "detail": "Object name does not match starter naming policy",
                }
            )
        if value in value_seen:
            findings.append(
                {
                    "type": "DUPLICATE_VALUE",
                    "name": name,
                    "detail": f"Same value as {value_seen[value]} -> {value}",
                }
            )
        else:
            value_seen[value] = name

    if settings.access_policy_id:
        rules = client.get_all(
            f"/api/fmc_config/v1/domain/{domain_uuid}"
            f"/policy/accesspolicies/{settings.access_policy_id}/accessrules"
        )
        for rule in rules:
            name = rule.get("name", "")
            if not rule.get("logEnd", False):
                findings.append(
                    {
                        "type": "RULE_LOGGING",
                        "name": name,
                        "detail": "Rule does not have logEnd enabled",
                    }
                )
            comments = rule.get("metadata", {}).get("comments", [])
            if not comments and not rule.get("newComments"):
                findings.append(
                    {
                        "type": "RULE_COMMENT",
                        "name": name,
                        "detail": "Rule has no comment in API response",
                    }
                )

    out = write_csv("outputs/reports/compliance_report.csv", findings)
    logger.info("Compliance report written to %s (%d findings)", out, len(findings))


if __name__ == "__main__":
    main()
