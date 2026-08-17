# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Read-only export of the access rules in a single FMC access policy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from common.cli import parse_args  # noqa: E402
from common.config import load_settings  # noqa: E402
from common.fmc_client import FMCClient  # noqa: E402
from common.logger import get_logger  # noqa: E402
from common.utils import write_json  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    parse_args("Export the access rules of one FMC access policy to outputs/reports/.")
    settings = load_settings()
    if not settings.access_policy_id:
        raise SystemExit("Set ACCESS_POLICY_ID in python/.env before running get_rules.py")
    client = FMCClient()
    domain_uuid = client.domain_uuid()
    rules = client.get_all(
        f"/api/fmc_config/v1/domain/{domain_uuid}"
        f"/policy/accesspolicies/{settings.access_policy_id}/accessrules"
    )
    write_json("outputs/reports/access_rules.json", {"items": rules})
    logger.info("Saved %d rules to outputs/reports/access_rules.json", len(rules))


if __name__ == "__main__":
    main()
