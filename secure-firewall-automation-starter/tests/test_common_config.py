# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Tests for python/common/. No live FMC required."""

from __future__ import annotations

import logging

import pytest

from common.config import Settings, as_bool, load_settings
from common.logger import RedactingFilter
from common.utils import validate_ip_or_network


def make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "fmc_host": "https://fmc.example.local",
        "username": "apiuser",
        "password": "unit-test-not-a-real-secret",
        "verify_ssl": True,
        "ca_bundle": None,
        "domain_uuid": None,
        "access_policy_id": None,
        "nat_policy_id": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


class TestAsBool:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "y", "on"])
    def test_truthy(self, value: str) -> None:
        assert as_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "No", "n", "off"])
    def test_falsy(self, value: str) -> None:
        assert as_bool(value) is False

    def test_missing_uses_default(self) -> None:
        assert as_bool(None, default=True) is True
        assert as_bool("  ", default=True) is True

    def test_garbage_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Cannot interpret"):
            as_bool("perhaps")


class TestLoadSettings:
    def test_tls_verification_defaults_to_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_HOST", "https://fmc.example.local")
        monkeypatch.setenv("FMC_USERNAME", "apiuser")
        monkeypatch.setenv("FMC_PASSWORD", "unit-test-not-a-real-secret")
        monkeypatch.delenv("VERIFY_SSL", raising=False)
        monkeypatch.delenv("FMC_CA_BUNDLE", raising=False)

        assert load_settings().verify_ssl is True

    def test_tls_can_be_disabled_explicitly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_HOST", "https://fmc.example.local")
        monkeypatch.setenv("VERIFY_SSL", "false")
        monkeypatch.delenv("FMC_CA_BUNDLE", raising=False)

        assert load_settings().verify_ssl is False

    def test_trailing_slash_is_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_HOST", "https://fmc.example.local/")
        monkeypatch.delenv("FMC_CA_BUNDLE", raising=False)

        assert load_settings().fmc_host == "https://fmc.example.local"

    def test_missing_ca_bundle_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_HOST", "https://fmc.example.local")
        monkeypatch.setenv("FMC_CA_BUNDLE", "/nonexistent/ca.pem")

        with pytest.raises(ValueError, match="FMC_CA_BUNDLE"):
            load_settings()


class TestVerifyProperty:
    def test_ca_bundle_wins_over_the_boolean(self, tmp_path) -> None:
        bundle = tmp_path / "ca.pem"
        bundle.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")

        assert make_settings(ca_bundle=str(bundle), verify_ssl=False).verify == str(bundle)

    def test_falls_back_to_the_boolean(self) -> None:
        assert make_settings(verify_ssl=True).verify is True
        assert make_settings(verify_ssl=False).verify is False


class TestRedactingFilter:
    @pytest.mark.parametrize(
        ("message", "secret"),
        [
            ("X-auth-access-token: abc123def456", "abc123def456"),
            ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
            ('{"password": "hunter2"}', "hunter2"),
            ("api_key=sk-secret-value", "sk-secret-value"),
            ("https://apiuser:hunter2@fmc.example.local/api", "hunter2"),
        ],
    )
    def test_secrets_never_reach_a_handler(self, message: str, secret: str) -> None:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, message, None, None)

        assert RedactingFilter().filter(record) is True
        assert secret not in str(record.msg)
        assert "<redacted>" in str(record.msg)

    def test_ordinary_messages_are_untouched(self) -> None:
        message = "Created object APP1_NET 10.10.20.0/24"
        record = logging.LogRecord("t", logging.INFO, __file__, 1, message, None, None)

        RedactingFilter().filter(record)

        assert record.msg == message

    def test_arguments_are_redacted_too(self) -> None:
        record = logging.LogRecord(
            "t", logging.INFO, __file__, 1, "detail %s", ("password=hunter2",), None
        )

        RedactingFilter().filter(record)

        assert "hunter2" not in str(record.args)


class TestValidateIpOrNetwork:
    @pytest.mark.parametrize(
        "value", ["10.10.10.10", "10.10.20.0/24", "192.0.2.1", "2001:db8::1", "2001:db8::/32"]
    )
    def test_accepts_valid_values(self, value: str) -> None:
        assert validate_ip_or_network(value) is True

    @pytest.mark.parametrize(
        "value", ["", "not-an-ip", "10.10.10.999", "10.10.10.0/33", "10.10.10.10-20"]
    )
    def test_rejects_invalid_values(self, value: str) -> None:
        assert validate_ip_or_network(value) is False

    def test_non_strict_networks_are_accepted(self) -> None:
        assert validate_ip_or_network("10.10.20.5/24") is True
