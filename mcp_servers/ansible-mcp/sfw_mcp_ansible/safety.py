# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Guardrails: write gate, plan-bound confirmation tokens, and redaction.

Same contract as the other servers in this repository. Mutations are split into a dry
run that issues a token bound to the resulting change set, and a real run that recomputes
the token. A model cannot change anything in one call.
"""

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

DEFAULT_TOKEN_TTL_SECONDS = 600
MAX_RESPONSE_CHARS = 200_000

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"((?:ansible_httpapi_pass|ansible_password|ansible_become_pass)\"?\s*[:=]\s*\"?)[^\s,\"'}]+",
            re.I,
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"((?:password|passwd|secret|api[_-]?key|token)\"?\s*[:=]\s*\"?)[^\s,\"'}]+", re.I
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(r"(X-auth-(?:access|refresh)-token\"?\s*[:=]\s*\"?)[^\s,\"'}]+", re.I),
        r"\1<redacted>",
    ),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
    (re.compile(r"\$ANSIBLE_VAULT[;0-9A-Za-z,.]*[\s0-9a-f]+", re.M), "<redacted-vault-blob>"),
)


class RunsDisabledError(PermissionError):
    """Raised when a real playbook run is attempted but runs are not enabled."""


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
    dropped = len(payload) - limit
    return f"{head}\n... [truncated {dropped} characters from the middle] ...\n{tail}"


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
            "Show the dry-run result to a human before running for real. Pass this token "
            "unchanged, together with the identical plan, to run_playbook."
        ),
    }


def verify_token(plan: Any, token: str | None) -> None:
    if not token:
        raise ConfirmationError(
            "No confirmation_token supplied. Run dry_run_playbook first, have a human "
            "review the changes, then call run_playbook with the token."
        )
    try:
        expiry_text, digest = token.strip().split(".", 1)
        expires_at = int(expiry_text)
    except ValueError as exc:
        raise ConfirmationError("Malformed confirmation_token.") from exc

    if time.time() > expires_at:
        raise ConfirmationError(
            "confirmation_token has expired. Re-run dry_run_playbook; the environment may "
            "have changed since the dry run."
        )

    expected = hmac.new(
        _SIGNING_KEY, f"{expires_at}:{canonical(plan)}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, digest):
        raise ConfirmationError(
            "confirmation_token does not authorise this playbook and these variables. "
            "Re-run dry_run_playbook."
        )


def require_runs_enabled(env_var: str = "ANSIBLE_MCP_ALLOW_RUN") -> None:
    if (os.getenv(env_var) or "").strip().lower() not in {"1", "true", "yes", "y", "on"}:
        raise RunsDisabledError(
            f"Real playbook execution is disabled. This server can only syntax-check and "
            f"dry-run until {env_var}=true is set in its environment. That is a deliberate "
            "default: enable it only when you intend an agent to change firewall "
            "configuration, and only against a lab first."
        )


def audit(tool: str, playbook: str, detail: dict[str, Any]) -> None:
    logger.info("tool=%s playbook=%s detail=%s", tool, playbook, redact(canonical(detail)))
