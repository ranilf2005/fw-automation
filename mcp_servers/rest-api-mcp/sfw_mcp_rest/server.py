# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""MCP server exposing Cisco Secure Firewall (FMC) REST tooling to AI agents.

Read tools are always available. Every mutating tool is split into a ``preview_*`` and
an ``apply_*`` half and is disabled entirely unless ``FMC_ALLOW_WRITES=true``.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import sys
from typing import Any

from fastmcp import FastMCP

from .config import ConfigError, FMCProfile, load_profiles, resolve_profile, writes_enabled
from .fmc import FMCClient, FMCError, matches_indicator
from .safety import (
    ConfirmationError,
    WritesDisabledError,
    audit,
    issue_token,
    redact,
    require_writes_enabled,
    verify_token,
)

# stdio transport reserves stdout for MCP traffic; everything else goes to stderr.
logging.basicConfig(
    stream=sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sfw_mcp_rest")

mcp: FastMCP = FastMCP(
    name="cisco-secure-firewall-rest",
    instructions=(
        "Tools for Cisco Secure Firewall Management Center over its REST API. "
        "Call list_fmc_profiles first to choose a target. Everything is read-only "
        "unless the operator enabled writes; to change objects you must call "
        "preview_object_changes, show the returned plan to the user, and only then call "
        "apply_object_changes with the confirmation token."
    ),
)

_PROFILES: dict[str, FMCProfile] | None = None
_CLIENTS: dict[str, FMCClient] = {}

VALID_OBJECT_TYPES = {"Host", "Network"}


def _profiles() -> dict[str, FMCProfile]:
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = load_profiles()
        logger.info("Loaded FMC profiles: %s", sorted(_PROFILES))
    return _PROFILES


async def _client(fmc_profile: str | None) -> FMCClient:
    profile = resolve_profile(_profiles(), fmc_profile)
    if profile.id not in _CLIENTS:
        _CLIENTS[profile.id] = FMCClient(profile)
    return _CLIENTS[profile.id]


def _fail(exc: Exception) -> dict[str, Any]:
    """Turn an exception into a structured, redacted tool result."""
    return {"ok": False, "error": type(exc).__name__, "message": redact(str(exc))}


def _summarise(item: dict[str, Any]) -> dict[str, Any]:
    """Trim an FMC object down to the fields an agent actually reasons about."""
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "type": item.get("type"),
        "value": item.get("value"),
        "description": item.get("description"),
    }


# --------------------------------------------------------------------------------------
# Read-only tools
# --------------------------------------------------------------------------------------


@mcp.tool
async def list_fmc_profiles() -> dict[str, Any]:
    """List the configured FMC instances this server can talk to.

    Always call this first. Use the returned ``id`` (or any alias) as the
    ``fmc_profile`` argument to the other tools.
    """
    try:
        profiles = _profiles()
    except ConfigError as exc:
        return _fail(exc)
    return {
        "ok": True,
        "writes_enabled": writes_enabled(),
        "default_profile": os.getenv("FMC_PROFILE_DEFAULT"),
        "profiles": [p.public() for p in profiles.values()],
    }


@mcp.tool
async def get_inventory(fmc_profile: str | None = None) -> dict[str, Any]:
    """Summarise an FMC: domain, managed devices, access policies, and object counts.

    Read-only. Use this to orient yourself before any other call.
    """
    try:
        client = await _client(fmc_profile)
        domain = await client.domain_uuid()
        devices = await client.get_all(await client.config_path("/devices/devicerecords"))
        policies = await client.get_all(await client.config_path("/policy/accesspolicies"))
        hosts = await client.get_all(await client.config_path("/object/hosts"))
        networks = await client.get_all(await client.config_path("/object/networks"))
        services = await client.get_all(await client.config_path("/object/protocolportobjects"))
        zones = await client.get_all(await client.config_path("/object/securityzones"))
    except (ConfigError, FMCError) as exc:
        return _fail(exc)

    audit("get_inventory", client.profile.id, {"devices": len(devices)})
    return {
        "ok": True,
        "profile": client.profile.id,
        "domain_uuid": domain,
        "counts": {
            "devices": len(devices),
            "access_policies": len(policies),
            "hosts": len(hosts),
            "networks": len(networks),
            "service_objects": len(services),
            "security_zones": len(zones),
        },
        "devices": [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "model": d.get("model"),
                "sw_version": d.get("sw_version"),
                "health": d.get("healthStatus"),
            }
            for d in devices
        ],
        "access_policies": [{"id": p.get("id"), "name": p.get("name")} for p in policies],
        "security_zones": [z.get("name") for z in zones],
    }


@mcp.tool
async def search_objects(
    indicator: str,
    fmc_profile: str | None = None,
    object_type: str = "any",
) -> dict[str, Any]:
    """Find network, host, or service objects by name, value, or IP containment.

    ``indicator`` may be an object name fragment, an IP address, a CIDR, or an FQDN.
    An IP address also matches any network object whose subnet contains it, which is
    the usual way to answer "which object covers this host?".

    ``object_type`` is one of ``any``, ``host``, ``network``, ``service``.
    Read-only.
    """
    if not indicator.strip():
        return {"ok": False, "error": "ValueError", "message": "indicator must not be empty."}

    wanted = object_type.strip().lower()
    sources = {
        "host": "/object/hosts",
        "network": "/object/networks",
        "service": "/object/protocolportobjects",
    }
    if wanted != "any" and wanted not in sources:
        return {
            "ok": False,
            "error": "ValueError",
            "message": f"object_type must be one of: any, {', '.join(sources)}",
        }

    try:
        client = await _client(fmc_profile)
        matches: list[dict[str, Any]] = []
        for kind, suffix in sources.items():
            if wanted not in ("any", kind):
                continue
            for item in await client.get_all(await client.config_path(suffix)):
                name = str(item.get("name", ""))
                value = str(item.get("value", "") or item.get("port", ""))
                if indicator.lower() in name.lower() or matches_indicator(value, indicator):
                    matches.append({**_summarise(item), "object_class": kind})
    except (ConfigError, FMCError) as exc:
        return _fail(exc)

    audit("search_objects", client.profile.id, {"indicator": indicator, "hits": len(matches)})
    return {
        "ok": True,
        "profile": client.profile.id,
        "indicator": indicator,
        "match_count": len(matches),
        "matches": matches,
    }


@mcp.tool
async def find_object_usage(
    object_name: str,
    access_policy: str,
    fmc_profile: str | None = None,
) -> dict[str, Any]:
    """Find which access rules reference an object, so you know if it is safe to remove.

    ``access_policy`` is a policy name or id from :func:`get_inventory`.
    Read-only.
    """
    try:
        client = await _client(fmc_profile)
        policy = await _find_policy(client, access_policy)
        if policy is None:
            return {
                "ok": False,
                "error": "LookupError",
                "message": f"No access policy matched {access_policy!r}.",
            }
        rules = await client.get_all(
            await client.config_path(f"/policy/accesspolicies/{policy['id']}/accessrules")
        )
    except (ConfigError, FMCError) as exc:
        return _fail(exc)

    needle = object_name.strip().lower()
    used_in: list[dict[str, Any]] = []
    for rule in rules:
        fields = [
            field
            for field in (
                "sourceNetworks",
                "destinationNetworks",
                "sourceZones",
                "destinationZones",
                "destinationPorts",
                "sourcePorts",
            )
            if any(
                str(obj.get("name", "")).lower() == needle
                for obj in (rule.get(field) or {}).get("objects", [])
            )
        ]
        if fields:
            used_in.append(
                {
                    "rule_name": rule.get("name"),
                    "rule_id": rule.get("id"),
                    "action": rule.get("action"),
                    "enabled": rule.get("enabled"),
                    "referenced_in": fields,
                }
            )

    audit("find_object_usage", client.profile.id, {"object": object_name, "hits": len(used_in)})
    return {
        "ok": True,
        "profile": client.profile.id,
        "object_name": object_name,
        "access_policy": policy.get("name"),
        "rules_scanned": len(rules),
        "reference_count": len(used_in),
        "safe_to_delete": not used_in,
        "referenced_by": used_in,
    }


@mcp.tool
async def list_access_rules(
    access_policy: str,
    fmc_profile: str | None = None,
    action: str | None = None,
    enabled_only: bool = False,
    limit: int = 200,
) -> dict[str, Any]:
    """List the access rules in a policy, newest ordering preserved.

    Optionally filter by ``action`` (ALLOW, BLOCK, TRUST, MONITOR) and to enabled rules.
    Read-only.
    """
    try:
        client = await _client(fmc_profile)
        policy = await _find_policy(client, access_policy)
        if policy is None:
            return {
                "ok": False,
                "error": "LookupError",
                "message": f"No access policy matched {access_policy!r}.",
            }
        rules = await client.get_all(
            await client.config_path(f"/policy/accesspolicies/{policy['id']}/accessrules")
        )
    except (ConfigError, FMCError) as exc:
        return _fail(exc)

    wanted_action = action.strip().upper() if action else None
    selected = [
        {
            "name": r.get("name"),
            "id": r.get("id"),
            "action": r.get("action"),
            "enabled": r.get("enabled"),
            "log_begin": r.get("logBegin"),
            "log_end": r.get("logEnd"),
            "source_zones": _names(r, "sourceZones"),
            "destination_zones": _names(r, "destinationZones"),
            "source_networks": _names(r, "sourceNetworks"),
            "destination_networks": _names(r, "destinationNetworks"),
            "destination_ports": _names(r, "destinationPorts"),
        }
        for r in rules
        if (not wanted_action or str(r.get("action", "")).upper() == wanted_action)
        and (not enabled_only or r.get("enabled"))
    ]

    return {
        "ok": True,
        "profile": client.profile.id,
        "access_policy": policy.get("name"),
        "total_rules": len(rules),
        "returned": len(selected[:limit]),
        "rules": selected[:limit],
    }


@mcp.tool
async def get_deployment_status(fmc_profile: str | None = None) -> dict[str, Any]:
    """Report devices with undeployed configuration changes.

    Use this after any change to confirm whether a deployment is still pending.
    Read-only.
    """
    try:
        client = await _client(fmc_profile)
        pending = await client.get_all(await client.config_path("/deployment/deployabledevices"))
    except (ConfigError, FMCError) as exc:
        return _fail(exc)

    return {
        "ok": True,
        "profile": client.profile.id,
        "pending_device_count": len(pending),
        "pending_devices": [
            {
                "name": d.get("name"),
                "id": d.get("device", {}).get("id") or d.get("id"),
                "version": d.get("version"),
            }
            for d in pending
        ],
        "note": "This server does not trigger deployments. Deploy from FMC after review.",
    }


# --------------------------------------------------------------------------------------
# Change pipeline: preview -> human review -> apply
# --------------------------------------------------------------------------------------


@mcp.tool
async def preview_object_changes(
    objects: list[dict[str, str]],
    fmc_profile: str | None = None,
) -> dict[str, Any]:
    """Work out what creating these network/host objects would do. Changes nothing.

    Each entry needs ``name``, ``type`` (``Host`` or ``Network``), ``value``, and an
    optional ``description``. The result classifies every entry as ``create``,
    ``skip_exists``, or ``invalid``, and returns a ``confirmation_token`` to pass to
    :func:`apply_object_changes`.

    Read-only: this tool is safe to call even when writes are disabled.
    """
    if not objects:
        return {"ok": False, "error": "ValueError", "message": "objects must not be empty."}

    try:
        client = await _client(fmc_profile)
        existing = {
            str(item.get("name")): item
            for suffix in ("/object/hosts", "/object/networks")
            for item in await client.get_all(await client.config_path(suffix))
        }
    except (ConfigError, FMCError) as exc:
        return _fail(exc)

    plan: list[dict[str, Any]] = []
    for entry in objects:
        name = str(entry.get("name", "")).strip()
        obj_type = str(entry.get("type", "")).strip().title()
        value = str(entry.get("value", "")).strip()
        description = str(entry.get("description", "")).strip()

        reason = _validate_object(name, obj_type, value)
        if reason:
            plan.append({"action": "invalid", "name": name, "value": value, "reason": reason})
        elif name in existing:
            plan.append(
                {
                    "action": "skip_exists",
                    "name": name,
                    "value": value,
                    "reason": f"already exists with value {existing[name].get('value')!r}",
                }
            )
        else:
            plan.append(
                {
                    "action": "create",
                    "name": name,
                    "type": obj_type,
                    "value": value,
                    "description": description,
                }
            )

    creates = [p for p in plan if p["action"] == "create"]
    audit("preview_object_changes", client.profile.id, {"planned": len(creates)})

    result = {
        "ok": True,
        "profile": client.profile.id,
        "summary": {
            "create": len(creates),
            "skip_exists": sum(1 for p in plan if p["action"] == "skip_exists"),
            "invalid": sum(1 for p in plan if p["action"] == "invalid"),
        },
        "plan": plan,
        "writes_enabled": writes_enabled(),
    }
    result.update(issue_token(plan))
    return result


@mcp.tool
async def apply_object_changes(
    plan: list[dict[str, Any]],
    confirmation_token: str,
    fmc_profile: str | None = None,
) -> dict[str, Any]:
    """Create the objects in a plan produced by :func:`preview_object_changes`.

    **This writes to FMC.** It requires ``FMC_ALLOW_WRITES=true`` and a matching,
    unexpired ``confirmation_token``. Pass the ``plan`` back exactly as it was returned;
    any modification invalidates the token.

    Only entries with ``action: create`` are acted on.
    """
    try:
        require_writes_enabled()
        verify_token(plan, confirmation_token)
        client = await _client(fmc_profile)
    except (WritesDisabledError, ConfirmationError, ConfigError) as exc:
        return _fail(exc)

    results: list[dict[str, Any]] = []
    for entry in plan:
        if entry.get("action") != "create":
            continue
        name = str(entry.get("name"))
        obj_type = str(entry.get("type"))
        suffix = "/object/hosts" if obj_type == "Host" else "/object/networks"
        payload = {
            "name": name,
            "type": obj_type,
            "value": entry.get("value"),
            "description": entry.get("description", ""),
        }
        try:
            created = await client.post(await client.config_path(suffix), payload)
            results.append({"name": name, "status": "created", "id": created.get("id")})
        except FMCError as exc:
            results.append({"name": name, "status": "failed", "detail": redact(str(exc))})

    created = sum(1 for r in results if r["status"] == "created")
    audit("apply_object_changes", client.profile.id, {"created": created})
    logger.warning("Applied %d object creations to profile %s", created, client.profile.id)

    return {
        "ok": True,
        "profile": client.profile.id,
        "created": created,
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
        "next_step": (
            "Verify in the FMC GUI, then deploy. Call get_deployment_status to see "
            "pending devices."
        ),
    }


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _names(rule: dict[str, Any], field: str) -> list[str]:
    return [str(o.get("name")) for o in (rule.get(field) or {}).get("objects", [])] or ["any"]


def _validate_object(name: str, obj_type: str, value: str) -> str | None:
    """Return a human-readable reason the object is invalid, or ``None`` if it is fine."""
    if not name:
        return "name is required"
    if obj_type not in VALID_OBJECT_TYPES:
        return f"type must be one of {sorted(VALID_OBJECT_TYPES)}, got {obj_type!r}"
    if not value:
        return "value is required"
    try:
        if obj_type == "Network":
            network = ipaddress.ip_network(value, strict=False)
            if network.prefixlen == network.max_prefixlen:
                return "a single address should use type Host, not Network"
        else:
            ipaddress.ip_address(value)
    except ValueError:
        expected = "CIDR network" if obj_type == "Network" else "IP address"
        return f"value {value!r} is not a valid {expected}"
    return None


async def _find_policy(client: FMCClient, wanted: str) -> dict[str, Any] | None:
    needle = wanted.strip().lower()
    for policy in await client.get_all(await client.config_path("/policy/accesspolicies")):
        if needle in (str(policy.get("name", "")).lower(), str(policy.get("id", "")).lower()):
            return policy
    return None


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def main() -> None:
    transport = (os.getenv("MCP_TRANSPORT") or "stdio").strip().lower()
    if transport == "http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8000"))
        if host not in LOOPBACK_HOSTS:
            logger.warning(
                "Binding %s exposes this server beyond localhost. It has no built-in "
                "authentication - front it with a TLS-terminating authenticating proxy.",
                host,
            )
        logger.info("Serving MCP over HTTP on %s:%s/mcp", host, port)
        mcp.run(transport="http", host=host, port=port)
    else:
        logger.info("Serving MCP over stdio")
        mcp.run()


if __name__ == "__main__":
    main()
