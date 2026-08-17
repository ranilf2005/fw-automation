# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Shared logging setup with credential redaction."""

from __future__ import annotations

import logging
import os
import re

from .config import ROOT

# Patterns that must never reach a log file or the console.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(X-auth-(?:access|refresh)-token[\"']?\s*[:=]\s*[\"']?)[^\s,\"'}]+", re.I),
        r"\1<redacted>",
    ),
    (
        re.compile(r"(Authorization[\"']?\s*[:=]\s*[\"']?)(?:Basic|Bearer)?\s*[^\s,\"'}]+", re.I),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"((?:password|passwd|secret|api[_-]?key|token)[\"']?\s*[:=]\s*[\"']?)[^\s,\"'}]+", re.I
        ),
        r"\1<redacted>",
    ),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
)


class RedactingFilter(logging.Filter):
    """Strip credentials and tokens out of log records before they are emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(self.redact(str(a)) for a in record.args)
        return True

    @staticmethod
    def redact(text: str) -> str:
        for pattern, replacement in _REDACTIONS:
            text = pattern.sub(replacement, text)
        return text


def get_logger(name: str) -> logging.Logger:
    logs_dir = ROOT / "outputs" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "automation.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    redactor = RedactingFilter()

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redactor)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redactor)
    logger.addHandler(console_handler)
    return logger
