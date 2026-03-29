from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.config import load_settings
from common.fmc_client import FMCClient
from common.utils import write_json


def main() -> None:
    settings = load_settings()
    if not settings.access_policy_id:
        raise SystemExit("Set ACCESS_POLICY_ID in python/.env before running get_rules.py")
    client = FMCClient()
    domain_uuid = client.domain_uuid()
    rules = client.get(
        f"/api/fmc_config/v1/domain/{domain_uuid}/policy/accesspolicies/{settings.access_policy_id}/accessrules",
        params={"limit": 1000},
    )
    write_json("outputs/reports/access_rules.json", rules)
    print("Saved outputs/reports/access_rules.json")


if __name__ == "__main__":
    main()
