# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Tests for the write-gate, confirmation tokens, and redaction."""

from __future__ import annotations

import time

import pytest

from sfw_mcp_rest.safety import (
    ConfirmationError,
    WritesDisabledError,
    canonical,
    issue_token,
    redact,
    require_writes_enabled,
    truncate,
    verify_token,
)

PLAN = [{"action": "create", "name": "APP1_NET", "type": "Network", "value": "10.10.20.0/24"}]


class TestWriteGate:
    def test_blocks_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FMC_ALLOW_WRITES", raising=False)
        with pytest.raises(WritesDisabledError):
            require_writes_enabled()

    @pytest.mark.parametrize("value", ["false", "0", "no", "off", "", "maybe"])
    def test_only_explicit_opt_in_unlocks(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("FMC_ALLOW_WRITES", value)
        with pytest.raises(WritesDisabledError):
            require_writes_enabled()

    def test_allows_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_ALLOW_WRITES", "true")
        require_writes_enabled()


class TestConfirmationToken:
    def test_round_trip(self) -> None:
        token = issue_token(PLAN)["confirmation_token"]
        verify_token(PLAN, token)

    def test_missing_token_is_rejected(self) -> None:
        with pytest.raises(ConfirmationError, match="No confirmation_token"):
            verify_token(PLAN, None)

    def test_malformed_token_is_rejected(self) -> None:
        with pytest.raises(ConfirmationError, match="Malformed"):
            verify_token(PLAN, "not-a-token")

    def test_token_does_not_authorise_a_different_plan(self) -> None:
        token = issue_token(PLAN)["confirmation_token"]
        tampered = [{**PLAN[0], "value": "0.0.0.0/0"}]

        with pytest.raises(ConfirmationError, match="does not authorise"):
            verify_token(tampered, token)

    def test_expired_token_is_rejected(self) -> None:
        token = issue_token(PLAN, ttl_seconds=-1)["confirmation_token"]
        with pytest.raises(ConfirmationError, match="expired"):
            verify_token(PLAN, token)

    def test_ttl_is_reported(self) -> None:
        issued = issue_token(PLAN, ttl_seconds=120)
        assert issued["ttl_seconds"] == 120
        assert issued["expires_at"] >= int(time.time()) + 119

    def test_key_ordering_does_not_change_the_token(self) -> None:
        reordered = [
            {"value": "10.10.20.0/24", "type": "Network", "name": "APP1_NET", "action": "create"}
        ]
        assert canonical(PLAN) == canonical(reordered)
        verify_token(reordered, issue_token(PLAN)["confirmation_token"])


class TestRedaction:
    @pytest.mark.parametrize(
        "text",
        [
            "X-auth-access-token: abc123def456",
            "Authorization: Basic dXNlcjpwYXNz",
            '{"password": "hunter2"}',
            "api_key=sk-secret-value",
            "https://apiuser:hunter2@fmc.example.local/api",
        ],
    )
    def test_secrets_are_stripped(self, text: str) -> None:
        cleaned = redact(text)
        for secret in ("abc123def456", "dXNlcjpwYXNz", "hunter2", "sk-secret-value"):
            assert secret not in cleaned
        assert "<redacted>" in cleaned

    def test_ordinary_text_survives(self) -> None:
        assert redact("Created object APP1_NET 10.10.20.0/24") == (
            "Created object APP1_NET 10.10.20.0/24"
        )


class TestTruncation:
    def test_short_payload_is_untouched(self) -> None:
        assert truncate("short", limit=100) == "short"

    def test_long_payload_is_capped(self) -> None:
        result = truncate("x" * 500, limit=100)
        assert len(result) < 500
        assert "truncated" in result
