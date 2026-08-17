# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Guardrails shared by every mutating tool.

The central idea: a model must never be able to change a firewall in a single call.
Mutations are split into a ``preview_*`` tool that returns a plan plus a
:func:`issue_token` confirmation token, and an ``apply_*`` tool that recomputes the
token from the plan it was handed. A stale, forged, or substituted plan fails closed.

The signing key is generated per process, so tokens do not survive a restart. That is
deliberate - a plan is only valid against the FMC state it was computed from.
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

# A plan older than this is rejected; FMC state may have moved on.
DEFAULT_TOKEN_TTL_SECONDS = 300

# Cap on any single tool response, so a runaway result cannot flood the model context.
MAX_RESPONSE_CHARS = 200_000

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(X-auth-(?:access|refresh)-token\"?\s*[:=]\s*\"?)[^\s,\"'}]+", re.I),
        r"\1<redacted>",
    ),
    (
        re.compile(r"(authorization\"?\s*[:=]\s*\"?)(?:basic|bearer)?\s*[^\s,\"'}]+", re.I),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"((?:password|passwd|secret|api[_-]?key|token)\"?\s*[:=]\s*\"?)[^\s,\"'}]+", re.I
        ),
        r"\1<redacted>",
    ),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
)


class WritesDisabledError(PermissionError):
    """Raised when a mutating tool is called but writes are not enabled."""


class ConfirmationError(ValueError):
    """Raised when a confirmation token is missing, expired, or does not match."""


def redact(text: str) -> str:
    """Strip credentials and tokens out of anything headed for a log or a model."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def truncate(payload: str, limit: int = MAX_RESPONSE_CHARS) -> str:
    if len(payload) <= limit:
        return payload
    return (
        payload[:limit]
        + f"\n... [truncated {len(payload) - limit} characters; narrow your filters]"
    )


def canonical(plan: Any) -> str:
    """Stable JSON encoding so an identical plan always hashes identically."""
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), default=str)


def issue_token(plan: Any, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> dict[str, Any]:
    """Sign a plan and return the confirmation material to hand back to the caller."""
    expires_at = int(time.time()) + ttl_seconds
    digest = hmac.new(
        _SIGNING_KEY, f"{expires_at}:{canonical(plan)}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "confirmation_token": f"{expires_at}.{digest}",
        "expires_at": expires_at,
        "ttl_seconds": ttl_seconds,
        "note": (
            "Show this plan to a human before applying. Pass the token unchanged, with "
            "the identical plan, to the apply tool. It expires "
            f"in {ttl_seconds} seconds."
        ),
    }


def verify_token(plan: Any, token: str | None) -> None:
    """Raise :class:`ConfirmationError` unless ``token`` authorises exactly ``plan``."""
    if not token:
        raise ConfirmationError(
            "No confirmation_token supplied. Run the matching preview tool first, have a "
            "human review the plan, then call this tool again with the token."
        )
    try:
        expiry_text, digest = token.strip().split(".", 1)
        expires_at = int(expiry_text)
    except ValueError as exc:
        raise ConfirmationError("Malformed confirmation_token.") from exc

    if time.time() > expires_at:
        raise ConfirmationError(
            "confirmation_token has expired. Re-run the preview tool; FMC state may have "
            "changed since the plan was produced."
        )

    expected = hmac.new(
        _SIGNING_KEY, f"{expires_at}:{canonical(plan)}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, digest):
        raise ConfirmationError(
            "confirmation_token does not authorise this plan. The plan changed after it "
            "was previewed, or the token came from a different plan or a previous run of "
            "the server. Re-run the preview tool."
        )


def require_writes_enabled(env_var: str = "FMC_ALLOW_WRITES") -> None:
    """Fail closed unless the operator explicitly opted into write operations."""
    value = (os.getenv(env_var) or "").strip().lower()
    if value not in {"1", "true", "yes", "y", "on"}:
        raise WritesDisabledError(
            f"Write operations are disabled. This server is read-only until {env_var}=true "
            "is set in its environment. That is a deliberate default: set it only when you "
            "intend an agent to change firewall configuration, and only against a lab or a "
            "non-production policy first."
        )


def audit(tool: str, profile: str, detail: dict[str, Any]) -> None:
    """Record a tool invocation. Never include secret material in ``detail``."""
    logger.info("tool=%s profile=%s detail=%s", tool, profile, redact(canonical(detail)))
