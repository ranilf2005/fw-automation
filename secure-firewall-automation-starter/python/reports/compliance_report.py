from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.config import load_settings
from common.fmc_client import FMCClient
from common.utils import write_csv


def main() -> None:
    settings = load_settings()
    client = FMCClient()
    domain_uuid = client.domain_uuid()

    findings: list[dict[str, str]] = []

    hosts = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/hosts", params={"limit": 1000}).get("items", [])
    networks = client.get(f"/api/fmc_config/v1/domain/{domain_uuid}/object/networks", params={"limit": 1000}).get("items", [])

    # duplicate value checks
    value_seen: dict[str, str] = {}
    for item in hosts + networks:
        value = item.get("value", "")
        name = item.get("name", "")
        if not name.startswith(("APP_", "NET_", "HOST_", "APP", "DB", "DNS")):
            findings.append({"type": "NAMING", "name": name, "detail": "Object name does not match starter naming policy"})
        if value in value_seen:
            findings.append({"type": "DUPLICATE_VALUE", "name": name, "detail": f"Same value as {value_seen[value]} -> {value}"})
        else:
            value_seen[value] = name

    if settings.access_policy_id:
        rules = client.get(
            f"/api/fmc_config/v1/domain/{domain_uuid}/policy/accesspolicies/{settings.access_policy_id}/accessrules",
            params={"limit": 1000},
        ).get("items", [])
        for rule in rules:
            name = rule.get("name", "")
            if not rule.get("logEnd", False):
                findings.append({"type": "RULE_LOGGING", "name": name, "detail": "Rule does not have logEnd enabled"})
            comments = rule.get("metadata", {}).get("comments", [])
            if not comments and not rule.get("newComments"):
                findings.append({"type": "RULE_COMMENT", "name": name, "detail": "Rule has no comment in API response"})

    out = write_csv("outputs/reports/compliance_report.csv", findings)
    print(f"Compliance report written to {out}")


if __name__ == "__main__":
    main()
