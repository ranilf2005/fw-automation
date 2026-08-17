# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Guardrails: apply gate, plan-bound confirmation tokens, and redaction."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any

logger = logging.getLogger(__name__)

_SIGNING_KEY = secrets.token_bytes(32)

DEFAULT_TOKEN_TTL_SECONDS = 900
MAX_RESPONSE_CHARS = 200_000

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"((?:fmc_password|password|passwd|secret|api[_-]?key|token)\"?\s*[:=]\s*\"?)[^\s,\"'}]+",
            re.I,
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(r"(TF_VAR_[A-Za-z0-9_]*(?:password|secret|token|key)\s*[:=]\s*)\S+", re.I),
        r"\1<redacted>",
    ),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
)


class ApplyDisabledError(PermissionError):
    """Raised when apply is attempted but not enabled."""


class ConfirmationError(ValueError):
    """Raised when a confirmation token is missing, expired, or does not match."""


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def truncate(payload: str, limit: int = MAX_RESPONSE_CHARS) -> str:
    if len(payload) <= limit:
        return payload
    head = payload[: limit // 2]
    tail = payload[-limit // 2 :]
    return f"{head}\n... [truncated {len(payload) - limit} characters] ...\n{tail}"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def issue_token(plan: Any, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> dict[str, Any]:
    expires_at = int(time.time()) + ttl_seconds
    digest = hmac.new(
        _SIGNING_KEY, f"{expires_at}:{canonical(plan)}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "confirmation_token": f"{expires_at}.{digest}",
        "expires_at": expires_at,
        "ttl_seconds": ttl_seconds,
        "note": (
            "Show this change summary to a human before applying. Pass the token unchanged, "
            "with the identical summary, to apply_plan."
        ),
    }


def verify_token(plan: Any, token: str | None) -> None:
    if not token:
        raise ConfirmationError(
            "No confirmation_token supplied. Run plan_workspace first, have a human review "
            "the change summary, then call apply_plan with the token."
        )
    try:
        expiry_text, digest = token.strip().split(".", 1)
        expires_at = int(expiry_text)
    except ValueError as exc:
        raise ConfirmationError("Malformed confirmation_token.") from exc

    if time.time() > expires_at:
        raise ConfirmationError(
            "confirmation_token has expired. Re-run plan_workspace; infrastructure may have "
            "changed since the plan was produced."
        )

    expected = hmac.new(
        _SIGNING_KEY, f"{expires_at}:{canonical(plan)}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, digest):
        raise ConfirmationError(
            "confirmation_token does not authorise this change summary. Re-run plan_workspace."
        )


def require_apply_enabled(env_var: str = "TF_MCP_ALLOW_APPLY") -> None:
    if (os.getenv(env_var) or "").strip().lower() not in {"1", "true", "yes", "y", "on"}:
        raise ApplyDisabledError(
            f"terraform apply is disabled. This server can only init, validate, plan, and "
            f"show until {env_var}=true is set in its environment. That is a deliberate "
            "default: enable it only when you intend an agent to change firewall "
            "configuration, and only against a lab first."
        )


def audit(tool: str, workspace: str, detail: dict[str, Any]) -> None:
    logger.info("tool=%s workspace=%s detail=%s", tool, workspace, redact(canonical(detail)))
