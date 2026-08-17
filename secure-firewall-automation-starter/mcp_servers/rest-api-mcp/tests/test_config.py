# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Tests for profile loading and resolution. No live FMC required."""

from __future__ import annotations

import pytest

from sfw_mcp_rest.config import (
    ConfigError,
    FMCProfile,
    as_bool,
    load_profiles,
    resolve_profile,
    writes_enabled,
)


def make_profile(profile_id: str, **overrides: object) -> FMCProfile:
    defaults: dict[str, object] = {
        "id": profile_id,
        "base_url": "https://fmc.example.local",
        "username": "apiuser",
        "password": "unit-test-not-a-real-secret",
    }
    defaults.update(overrides)
    return FMCProfile(**defaults)  # type: ignore[arg-type]


class TestAsBool:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "y", "on"])
    def test_truthy(self, value: str) -> None:
        assert as_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "No", "n", "off"])
    def test_falsy(self, value: str) -> None:
        assert as_bool(value) is False

    def test_none_uses_default(self) -> None:
        assert as_bool(None, default=True) is True
        assert as_bool("", default=True) is True

    def test_garbage_is_rejected(self) -> None:
        with pytest.raises(ConfigError):
            as_bool("maybe")


class TestProfileLoading:
    def test_env_mode_defaults_to_tls_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FMC_PROFILES_DIR", raising=False)
        monkeypatch.setenv("FMC_BASE_URL", "https://fmc.example.local")
        monkeypatch.setenv("FMC_USERNAME", "apiuser")
        monkeypatch.setenv("FMC_PASSWORD", "unit-test-not-a-real-secret")
        monkeypatch.delenv("FMC_VERIFY_SSL", raising=False)

        profiles = load_profiles()

        assert set(profiles) == {"default"}
        assert profiles["default"].verify_ssl is True

    def test_plaintext_http_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FMC_PROFILES_DIR", raising=False)
        monkeypatch.setenv("FMC_BASE_URL", "http://fmc.example.local")
        monkeypatch.setenv("FMC_USERNAME", "apiuser")
        monkeypatch.setenv("FMC_PASSWORD", "unit-test-not-a-real-secret")

        with pytest.raises(ConfigError, match="https"):
            load_profiles()

    def test_missing_credentials_are_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FMC_PROFILES_DIR", raising=False)
        monkeypatch.setenv("FMC_BASE_URL", "https://fmc.example.local")
        monkeypatch.setenv("FMC_USERNAME", "apiuser")
        monkeypatch.delenv("FMC_PASSWORD", raising=False)

        with pytest.raises(ConfigError, match="FMC_PASSWORD"):
            load_profiles()

    def test_profile_directory_is_discovered(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "north.env").write_text(
            "FMC_PROFILE_ID=fmc-north\n"
            "FMC_PROFILE_ALIASES=north,dc1\n"
            "FMC_BASE_URL=https://north.example.local\n"
            "FMC_USERNAME=apiuser\n"
            "FMC_PASSWORD=unit-test-not-a-real-secret\n",
            encoding="utf-8",
        )
        (tmp_path / "south.env").write_text(
            "FMC_PROFILE_ID=fmc-south\n"
            "FMC_BASE_URL=https://south.example.local\n"
            "FMC_USERNAME=apiuser\n"
            "FMC_PASSWORD=unit-test-not-a-real-secret\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("FMC_PROFILES_DIR", str(tmp_path))

        profiles = load_profiles()

        assert set(profiles) == {"fmc-north", "fmc-south"}
        assert profiles["fmc-north"].aliases == ("north", "dc1")


class TestResolveProfile:
    def test_resolves_by_id_and_alias(self) -> None:
        profiles = {"fmc-north": make_profile("fmc-north", aliases=("north", "dc1"))}

        assert resolve_profile(profiles, "fmc-north").id == "fmc-north"
        assert resolve_profile(profiles, "DC1").id == "fmc-north"

    def test_single_profile_needs_no_argument(self) -> None:
        profiles = {"only": make_profile("only")}
        assert resolve_profile(profiles, None).id == "only"

    def test_ambiguous_selection_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FMC_PROFILE_DEFAULT", raising=False)
        profiles = {"a": make_profile("a"), "b": make_profile("b")}

        with pytest.raises(ConfigError, match="FMC_PROFILE_DEFAULT"):
            resolve_profile(profiles, None)

    def test_unknown_profile_is_rejected(self) -> None:
        with pytest.raises(ConfigError, match="Unknown FMC profile"):
            resolve_profile({"a": make_profile("a")}, "nope")


class TestSecrecy:
    def test_password_is_not_in_repr(self) -> None:
        assert "unit-test-not-a-real-secret" not in repr(make_profile("a"))

    def test_public_view_excludes_password(self) -> None:
        assert "password" not in make_profile("a").public()

    def test_ca_bundle_overrides_boolean_verify(self, tmp_path) -> None:
        bundle = tmp_path / "ca.pem"
        bundle.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
        profile = make_profile("a", ca_bundle=str(bundle), verify_ssl=False)

        assert profile.verify == str(bundle)


class TestWriteGate:
    def test_writes_are_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FMC_ALLOW_WRITES", raising=False)
        assert writes_enabled() is False

    def test_writes_can_be_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_ALLOW_WRITES", "true")
        assert writes_enabled() is True
