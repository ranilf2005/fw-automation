# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Minimal REST client for the Cisco Secure Firewall Management Center API."""

from __future__ import annotations

import warnings
from base64 import b64encode
from typing import Any

import requests

from .config import load_settings
from .logger import get_logger

logger = get_logger(__name__)

AUTH_PATH = "/api/fmc_platform/v1/auth/generatetoken"
REFRESH_PATH = "/api/fmc_platform/v1/auth/refreshtoken"


class FMCClient:
    """Thin, session-based wrapper around the FMC REST API.

    Authentication is token based: a POST to ``generatetoken`` with HTTP Basic
    credentials returns ``X-auth-access-token``, which is then sent on every
    subsequent request.
    """

    def __init__(self) -> None:
        self.settings = load_settings()
        missing = [
            name
            for name, value in (
                ("FMC_HOST", self.settings.fmc_host),
                ("FMC_USERNAME", self.settings.username),
                ("FMC_PASSWORD", self.settings.password),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Please populate python/.env with: {', '.join(missing)}")
        if not self.settings.fmc_host.startswith("https://"):
            raise ValueError(
                f"FMC_HOST must use https://, got {self.settings.fmc_host!r}. "
                "Sending API credentials over plaintext HTTP is not supported."
            )

        self.session = requests.Session()
        self.session.verify = self.settings.verify
        if self.settings.verify is False:
            warnings.warn(
                "TLS certificate verification is DISABLED (VERIFY_SSL=false). This "
                "exposes FMC credentials to machine-in-the-middle attacks. Use this "
                "only in a lab; prefer FMC_CA_BUNDLE to trust a private CA.",
                stacklevel=2,
            )
            logger.warning("TLS certificate verification is disabled - lab use only")

        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._domain_uuid: str | None = None

    def _url(self, path: str) -> str:
        return f"{self.settings.fmc_host}{path}"

    def authenticate(self) -> None:
        basic = b64encode(f"{self.settings.username}:{self.settings.password}".encode()).decode()
        response = self.session.post(
            self._url(AUTH_PATH),
            headers={"Authorization": f"Basic {basic}"},
            timeout=30,
        )
        response.raise_for_status()
        self.access_token = response.headers.get("X-auth-access-token")
        self.refresh_token = response.headers.get("X-auth-refresh-token")
        if not self.access_token:
            raise RuntimeError(
                "No X-auth-access-token returned. Confirm credentials and API access."
            )
        logger.info("Authenticated to FMC")

    def headers(self) -> dict[str, str]:
        if not self.access_token:
            self.authenticate()
        return {
            "X-auth-access-token": self.access_token or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
        timeout: int = 60,
    ) -> requests.Response:
        """Issue a request, re-authenticating once if the token has expired."""
        response = self.session.request(
            method,
            self._url(path),
            headers=self.headers(),
            params=params,
            json=json,
            timeout=timeout,
        )
        if response.status_code == 401:
            logger.info("FMC token rejected, re-authenticating")
            self.access_token = None
            response = self.session.request(
                method,
                self._url(path),
                headers=self.headers(),
                params=params,
                json=json,
                timeout=timeout,
            )
        response.raise_for_status()
        return response

    @staticmethod
    def _body(response: requests.Response) -> dict[str, Any]:
        if not response.text:
            return {}
        return response.json()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._body(self._request("GET", path, params=params))

    def get_all(self, path: str, page_size: int = 1000) -> list[dict[str, Any]]:
        """Follow FMC pagination and return every ``items`` entry.

        FMC caps ``limit`` per response, so a single ``get()`` silently truncates on
        large deployments. Use this whenever you need a complete list.
        """
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.get(path, params={"limit": page_size, "offset": offset})
            batch = page.get("items", [])
            items.extend(batch)
            paging = page.get("paging", {})
            count = int(paging.get("count", len(items)))
            if not batch or len(items) >= count:
                return items
            offset += len(batch)

    def post(self, path: str, payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        return self._body(self._request("POST", path, json=payload))

    def put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._body(self._request("PUT", path, json=payload))

    def delete(self, path: str) -> None:
        self._request("DELETE", path)

    def domain_uuid(self) -> str:
        if self.settings.domain_uuid:
            return self.settings.domain_uuid
        if self._domain_uuid:
            return self._domain_uuid
        domains = self.get("/api/fmc_platform/v1/info/domain")
        items = domains.get("items", [])
        if not items:
            raise RuntimeError("No FMC domain returned")
        self._domain_uuid = str(items[0]["uuid"])
        return self._domain_uuid

    def config_path(self, suffix: str) -> str:
        return f"/api/fmc_config/v1/domain/{self.domain_uuid()}{suffix}"
