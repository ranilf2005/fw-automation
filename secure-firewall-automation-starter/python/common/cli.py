# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Shared command-line handling so every script supports ``-h`` / ``--help``."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import ROOT
from .logger import set_level

EPILOG = """\
Configuration is read from python/.env (copy python/.env.example to start).
Required: FMC_HOST (https://, no trailing slash), FMC_USERNAME, FMC_PASSWORD.
TLS verification is on by default; set FMC_CA_BUNDLE to trust a private CA.

Reports are written to outputs/reports/ and logs to outputs/logs/automation.log.
"""


def _parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=description,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override LOG_LEVEL for this run.",
    )
    return parser


def parse_args(description: str) -> argparse.Namespace:
    """Parse arguments for a script that takes no input file."""
    args = _parser(description).parse_args()
    if args.log_level:
        set_level(args.log_level)
    return args


def parse_csv_args(description: str, default_rel: str) -> argparse.Namespace:
    """Parse arguments for a script that reads one CSV file.

    ``input`` is optional and falls back to ``default_rel`` inside the repository, so the
    documented examples keep working. The path is validated here rather than failing
    later inside pandas.
    """
    parser = _parser(description)
    parser.add_argument(
        "input",
        nargs="?",
        default=str(ROOT / default_rel),
        help=f"Path to the input CSV. Defaults to {default_rel}",
    )
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    if not path.is_file():
        parser.error(f"input CSV not found: {path}")
    args.input = path
    if args.log_level:
        set_level(args.log_level)
    return args
