from __future__ import annotations

from base64 import b64encode
from typing import Any
import requests
from .config import load_settings
from .logger import get_logger

logger = get_logger(__name__)


class FMCClient:
    def __init__(self) -> None:
        self.settings = load_settings()
        if not self.settings.fmc_host or not self.settings.username or not self.settings.password:
            raise ValueError("Please populate python/.env with FMC_HOST, FMC_USERNAME, and FMC_PASSWORD")
        self.session = requests.Session()
        self.session.verify = self.settings.verify_ssl
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    def _url(self, path: str) -> str:
        return f"{self.settings.fmc_host}{path}"

    def authenticate(self) -> None:
        url = self._url("/api/fmc_platform/v1/auth/generatetoken")
        basic = b64encode(f"{self.settings.username}:{self.settings.password}".encode()).decode()
        headers = {"Authorization": f"Basic {basic}"}
        response = self.session.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        self.access_token = response.headers.get("X-auth-access-token")
        self.refresh_token = response.headers.get("X-auth-refresh-token")
        if not self.access_token:
            raise RuntimeError("No X-auth-access-token returned. Confirm credentials and API access.")
        logger.info("Authenticated to FMC")

    def headers(self) -> dict[str, str]:
        if not self.access_token:
            self.authenticate()
        return {
            "X-auth-access-token": self.access_token or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(self._url(path), headers=self.headers(), params=params, timeout=60)
        response.raise_for_status()
        if response.text:
            return response.json()
        return {}

    def post(self, path: str, payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        response = self.session.post(self._url(path), headers=self.headers(), json=payload, timeout=60)
        response.raise_for_status()
        if response.text:
            return response.json()
        return {}

    def delete(self, path: str) -> None:
        response = self.session.delete(self._url(path), headers=self.headers(), timeout=60)
        response.raise_for_status()

    def domain_uuid(self) -> str:
        if self.settings.domain_uuid:
            return self.settings.domain_uuid
        domains = self.get("/api/fmc_platform/v1/info/domain")
        items = domains.get("items", [])
        if not items:
            raise RuntimeError("No FMC domain returned")
        return items[0]["uuid"]

    def config_path(self, suffix: str) -> str:
        return f"/api/fmc_config/v1/domain/{self.domain_uuid()}{suffix}"
