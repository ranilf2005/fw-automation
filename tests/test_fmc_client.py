# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Tests for the FMC client's transport safety and pagination.

The HTTP layer is stubbed with `responses`, so nothing here contacts a real FMC.
"""

from __future__ import annotations

import pytest
import responses

from common.fmc_client import FMCClient

HOST = "https://fmc.example.local"
TOKEN = "unit-test-access-token"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FMC_HOST", HOST)
    monkeypatch.setenv("FMC_USERNAME", "apiuser")
    monkeypatch.setenv("FMC_PASSWORD", "unit-test-not-a-real-secret")
    monkeypatch.setenv("VERIFY_SSL", "true")
    monkeypatch.delenv("FMC_CA_BUNDLE", raising=False)
    monkeypatch.delenv("FMC_DOMAIN_UUID", raising=False)


def stub_auth() -> None:
    responses.add(
        responses.POST,
        f"{HOST}/api/fmc_platform/v1/auth/generatetoken",
        headers={"X-auth-access-token": TOKEN, "X-auth-refresh-token": "refresh"},
        status=204,
    )


class TestConstruction:
    def test_requires_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_HOST", HOST)
        monkeypatch.delenv("FMC_USERNAME", raising=False)
        monkeypatch.delenv("FMC_PASSWORD", raising=False)
        monkeypatch.delenv("FMC_CA_BUNDLE", raising=False)

        with pytest.raises(ValueError, match="FMC_USERNAME"):
            FMCClient()

    def test_rejects_plaintext_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FMC_HOST", "http://fmc.example.local")
        monkeypatch.setenv("FMC_USERNAME", "apiuser")
        monkeypatch.setenv("FMC_PASSWORD", "unit-test-not-a-real-secret")
        monkeypatch.delenv("FMC_CA_BUNDLE", raising=False)

        with pytest.raises(ValueError, match="https"):
            FMCClient()

    def test_tls_verification_is_on_by_default(self, env: None) -> None:
        assert FMCClient().session.verify is True

    def test_disabling_tls_warns(self, env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VERIFY_SSL", "false")

        with pytest.warns(UserWarning, match="TLS certificate verification is DISABLED"):
            client = FMCClient()

        assert client.session.verify is False


class TestAuthentication:
    @responses.activate
    def test_token_is_sent_on_subsequent_calls(self, env: None) -> None:
        stub_auth()
        responses.add(
            responses.GET,
            f"{HOST}/api/fmc_platform/v1/info/domain",
            json={"items": [{"uuid": "domain-1"}]},
            status=200,
        )

        client = FMCClient()
        assert client.domain_uuid() == "domain-1"
        assert responses.calls[1].request.headers["X-auth-access-token"] == TOKEN

    @responses.activate
    def test_missing_token_header_is_an_error(self, env: None) -> None:
        responses.add(responses.POST, f"{HOST}/api/fmc_platform/v1/auth/generatetoken", status=204)

        with pytest.raises(RuntimeError, match="X-auth-access-token"):
            FMCClient().authenticate()

    @responses.activate
    def test_expired_token_triggers_one_retry(self, env: None) -> None:
        stub_auth()
        responses.add(responses.GET, f"{HOST}/api/test", status=401)
        stub_auth()
        responses.add(responses.GET, f"{HOST}/api/test", json={"ok": True}, status=200)

        assert FMCClient().get("/api/test") == {"ok": True}

    @responses.activate
    def test_domain_uuid_is_cached(self, env: None) -> None:
        stub_auth()
        responses.add(
            responses.GET,
            f"{HOST}/api/fmc_platform/v1/info/domain",
            json={"items": [{"uuid": "domain-1"}]},
            status=200,
        )

        client = FMCClient()
        assert client.domain_uuid() == client.domain_uuid() == "domain-1"
        domain_calls = [c for c in responses.calls if c.request.url.endswith("/info/domain")]
        assert len(domain_calls) == 1


class TestPagination:
    @responses.activate
    def test_get_all_follows_every_page(self, env: None) -> None:
        stub_auth()
        responses.add(
            responses.GET,
            f"{HOST}/api/objects",
            json={"items": [{"name": f"OBJ{i}"} for i in range(2)], "paging": {"count": 3}},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{HOST}/api/objects",
            json={"items": [{"name": "OBJ2"}], "paging": {"count": 3}},
            status=200,
        )

        assert [o["name"] for o in FMCClient().get_all("/api/objects")] == [
            "OBJ0",
            "OBJ1",
            "OBJ2",
        ]

    @responses.activate
    def test_empty_page_terminates(self, env: None) -> None:
        stub_auth()
        responses.add(
            responses.GET,
            f"{HOST}/api/objects",
            json={"items": [], "paging": {"count": 0}},
            status=200,
        )

        assert FMCClient().get_all("/api/objects") == []


class TestErrors:
    @responses.activate
    def test_http_error_propagates(self, env: None) -> None:
        import requests

        stub_auth()
        responses.add(responses.GET, f"{HOST}/api/objects", status=500)

        with pytest.raises(requests.HTTPError):
            FMCClient().get("/api/objects")

    @responses.activate
    def test_empty_body_returns_empty_dict(self, env: None) -> None:
        stub_auth()
        responses.add(responses.GET, f"{HOST}/api/objects", body="", status=200)

        assert FMCClient().get("/api/objects") == {}
