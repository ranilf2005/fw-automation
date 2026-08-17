# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Async FMC REST client used by the MCP tools."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from base64 import b64encode
from typing import Any

import httpx

from .config import MAX_PAGE_SIZE, MAX_RESULTS, FMCProfile

logger = logging.getLogger(__name__)

AUTH_PATH = "/api/fmc_platform/v1/auth/generatetoken"
PLATFORM = "/api/fmc_platform/v1"


class FMCError(RuntimeError):
    """An FMC API call failed."""


class FMCClient:
    """Token-authenticated client for a single FMC profile.

    One instance per profile is cached by the server; the access token is reused across
    tool calls and refreshed automatically when FMC rejects it.
    """

    def __init__(self, profile: FMCProfile, timeout: float = 60.0) -> None:
        self.profile = profile
        self._client = httpx.AsyncClient(
            base_url=profile.base_url,
            verify=profile.verify,
            timeout=timeout,
            follow_redirects=False,
        )
        self._token: str | None = None
        self._domain_uuid: str | None = profile.domain_uuid
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _authenticate(self) -> None:
        basic = b64encode(f"{self.profile.username}:{self.profile.password}".encode()).decode()
        response = await self._client.post(AUTH_PATH, headers={"Authorization": f"Basic {basic}"})
        if response.status_code >= 400:
            raise FMCError(
                f"Authentication to {self.profile.id} failed with HTTP "
                f"{response.status_code}. Check the API user's credentials and that REST "
                "API access is enabled for it."
            )
        token = response.headers.get("X-auth-access-token")
        if not token:
            raise FMCError("FMC did not return X-auth-access-token.")
        self._token = token
        logger.info("Authenticated to FMC profile %s", self.profile.id)

    async def _headers(self) -> dict[str, str]:
        async with self._lock:
            if not self._token:
                await self._authenticate()
        return {
            "X-auth-access-token": self._token or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> dict[str, Any]:
        """Issue a request, re-authenticating once if the token has expired."""
        for attempt in (1, 2):
            response = await self._client.request(
                method, path, headers=await self._headers(), params=params, json=json_body
            )
            if response.status_code == 401 and attempt == 1:
                logger.info("Token rejected for %s, re-authenticating", self.profile.id)
                async with self._lock:
                    self._token = None
                continue
            if response.status_code >= 400:
                raise FMCError(
                    f"{method} {path} returned HTTP {response.status_code}: "
                    f"{_error_detail(response)}"
                )
            if not response.content:
                return {}
            return response.json()
        raise FMCError(f"{method} {path} failed after re-authentication.")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, payload: Any) -> dict[str, Any]:
        return await self.request("POST", path, json_body=payload)

    async def get_all(self, path: str, max_results: int = MAX_RESULTS) -> list[dict[str, Any]]:
        """Follow FMC pagination, stopping at ``max_results`` so responses stay bounded."""
        items: list[dict[str, Any]] = []
        offset = 0
        while len(items) < max_results:
            page = await self.get(
                path, {"limit": MAX_PAGE_SIZE, "offset": offset, "expanded": True}
            )
            batch = page.get("items", []) or []
            items.extend(batch)
            total = int(page.get("paging", {}).get("count", len(items)))
            if not batch or len(items) >= total:
                break
            offset += len(batch)
        return items[:max_results]

    async def domain_uuid(self) -> str:
        if self._domain_uuid:
            return self._domain_uuid
        domains = await self.get(f"{PLATFORM}/info/domain")
        items = domains.get("items", [])
        if not items:
            raise FMCError("FMC returned no domains.")
        self._domain_uuid = str(items[0]["uuid"])
        return self._domain_uuid

    async def config_path(self, suffix: str) -> str:
        return f"/api/fmc_config/v1/domain/{await self.domain_uuid()}{suffix}"


def _error_detail(response: httpx.Response) -> str:
    """Pull FMC's error description out of the body without leaking headers."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    messages = body.get("error", {}).get("messages", [])
    if messages:
        return "; ".join(str(m.get("description", m)) for m in messages)[:500]
    return str(body)[:500]


def matches_indicator(value: str, indicator: str) -> bool:
    """Does an object's value match a search indicator?

    Handles plain substring matching plus IP-in-network containment, so searching for
    ``10.10.20.5`` also finds the object holding ``10.10.20.0/24``.
    """
    value = (value or "").strip()
    indicator = (indicator or "").strip()
    if not value or not indicator:
        return False
    if indicator.lower() in value.lower():
        return True
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        return False
    try:
        if "/" in indicator:
            return ipaddress.ip_network(indicator, strict=False).subnet_of(network)
        return ipaddress.ip_address(indicator) in network
    except (ValueError, TypeError):
        return False
