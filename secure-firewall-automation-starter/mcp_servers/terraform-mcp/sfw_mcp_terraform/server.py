# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""MCP server exposing Terraform workflows for Cisco Secure Firewall to AI agents.

Plan explanation and drift detection are read-only, which makes them an excellent fit
for a language model: dense JSON in, plain-English risk summary out, nothing changed.
``apply`` is disabled by default and additionally requires a plan-bound token.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from fastmcp import FastMCP

from .config import (
    ConfigError,
    apply_enabled,
    discover_workspaces,
    resolve_workspace,
    timeout_seconds,
)
from .runner import (
    PLAN_FILE,
    ExecutableNotFound,
    run_terraform,
    summarise_plan,
    summarise_state,
)
from .safety import (
    ApplyDisabledError,
    ConfirmationError,
    audit,
    issue_token,
    redact,
    require_apply_enabled,
    verify_token,
)

logging.basicConfig(
    stream=sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sfw_mcp_terraform")

mcp: FastMCP = FastMCP(
    name="cisco-secure-firewall-terraform",
    instructions=(
        "Terraform tooling for Cisco Secure Firewall. Call list_workspaces first. "
        "init, validate, plan, explain_plan, detect_drift, and show_state are read-only "
        "and safe. apply_plan changes infrastructure: it requires TF_MCP_ALLOW_APPLY=true "
        "and a confirmation token returned by plan_workspace. Always show the change "
        "summary to the user before applying, and call out destructive actions."
    ),
)


def _fail(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": type(exc).__name__, "message": redact(str(exc))}


@mcp.tool
async def list_workspaces() -> dict[str, Any]:
    """List the Terraform workspaces this server is allowed to operate on.

    Always call this first. Read-only.
    """
    try:
        workspaces = discover_workspaces()
        return {
            "ok": True,
            "apply_enabled": apply_enabled(),
            "timeout_seconds": timeout_seconds(),
            "workspaces": [w.public() for w in workspaces.values()],
        }
    except ConfigError as exc:
        return _fail(exc)


@mcp.tool
async def get_versions(workspace: str | None = None) -> dict[str, Any]:
    """Report the Terraform CLI and provider versions in use. Read-only."""
    try:
        target = resolve_workspace(workspace)
        result = await run_terraform(target, "version", "-json")
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": result.ok, "workspace": target.name, "raw": result.public()}

    return {
        "ok": result.ok,
        "workspace": target.name,
        "terraform_version": parsed.get("terraform_version"),
        "platform": parsed.get("platform"),
        "provider_selections": parsed.get("provider_selections", {}),
        "outdated": parsed.get("terraform_outdated"),
    }


@mcp.tool
async def init_workspace(workspace: str | None = None) -> dict[str, Any]:
    """Run ``terraform init -backend=false``: download providers, initialise modules.

    ``-backend=false`` means no remote state is contacted and no state is written, so
    this is safe to run for inspection.
    """
    try:
        target = resolve_workspace(workspace)
        result = await run_terraform(target, "init", "-backend=false", "-input=false", "-no-color")
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    audit("init_workspace", target.name, {"ok": result.ok})
    return {"ok": result.ok, "workspace": target.name, **result.public()}


@mcp.tool
async def validate_workspace(workspace: str | None = None) -> dict[str, Any]:
    """Run ``terraform validate``: check syntax, types, and provider schema conformance.

    Read-only, contacts no infrastructure. Returns structured diagnostics.
    """
    try:
        target = resolve_workspace(workspace)
        result = await run_terraform(target, "validate", "-json", "-no-color")
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": result.ok, "workspace": target.name, **result.public()}

    return {
        "ok": True,
        "workspace": target.name,
        "valid": bool(parsed.get("valid")),
        "error_count": parsed.get("error_count", 0),
        "warning_count": parsed.get("warning_count", 0),
        "diagnostics": [
            {
                "severity": d.get("severity"),
                "summary": d.get("summary"),
                "detail": d.get("detail"),
                "file": (d.get("range") or {}).get("filename"),
                "line": ((d.get("range") or {}).get("start") or {}).get("line"),
            }
            for d in parsed.get("diagnostics", [])
        ],
    }


@mcp.tool
async def plan_workspace(workspace: str | None = None) -> dict[str, Any]:
    """Run ``terraform plan``, save it, and return a compact sanitised change summary.

    Changes nothing. Values Terraform marked sensitive are replaced with
    ``<sensitive>`` before they reach you. Returns a ``confirmation_token`` for
    :func:`apply_plan`, plus ``is_destructive`` so you can warn the user prominently.
    """
    try:
        target = resolve_workspace(workspace)
        planned = await run_terraform(
            target, "plan", "-input=false", "-no-color", "-detailed-exitcode", f"-out={PLAN_FILE}"
        )
        # -detailed-exitcode: 0 = no changes, 1 = error, 2 = changes present.
        if planned.returncode == 1 or planned.timed_out:
            return {"ok": False, "workspace": target.name, "stage": "plan", **planned.public()}

        shown = await run_terraform(target, "show", "-json", PLAN_FILE)
        parsed = json.loads(shown.stdout) if shown.stdout else {}
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)
    except json.JSONDecodeError as exc:
        return _fail(ValueError(f"Could not parse the plan JSON: {exc}"))

    summary = summarise_plan(parsed)
    audit("plan_workspace", target.name, {"summary": summary["summary"]})

    response: dict[str, Any] = {
        "ok": True,
        "workspace": target.name,
        "plan_file": PLAN_FILE,
        "apply_enabled": apply_enabled(),
        **summary,
    }
    if summary["is_destructive"]:
        response["warning"] = (
            "This plan DELETES or REPLACES resources. Show the affected addresses to the "
            "user explicitly and get an unambiguous confirmation before applying."
        )
    response.update(issue_token(_token_payload(target.name, summary)))
    return response


@mcp.tool
async def explain_plan(workspace: str | None = None) -> dict[str, Any]:
    """Re-read the last saved plan and return it resource by resource. Read-only.

    Use this to talk a user through a plan without re-running it.
    """
    try:
        target = resolve_workspace(workspace)
        if not (target.path / PLAN_FILE).is_file():
            return {
                "ok": False,
                "error": "FileNotFoundError",
                "message": f"No saved plan in {target.name}. Run plan_workspace first.",
            }
        shown = await run_terraform(target, "show", "-json", PLAN_FILE)
        parsed = json.loads(shown.stdout) if shown.stdout else {}
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)
    except json.JSONDecodeError as exc:
        return _fail(ValueError(f"Could not parse the plan JSON: {exc}"))

    summary = summarise_plan(parsed)
    return {
        "ok": True,
        "workspace": target.name,
        "narrative": [
            f"{change['action'].upper()} {change['address']}"
            + (
                f" (attributes: {', '.join(change['changed_attributes'])})"
                if change["changed_attributes"]
                else ""
            )
            for change in summary["changes"]
        ],
        **summary,
    }


@mcp.tool
async def detect_drift(workspace: str | None = None) -> dict[str, Any]:
    """Refresh state against FMC and report what changed outside Terraform. Read-only.

    This is the "did somebody change it in the GUI?" check. It writes no configuration,
    though it does refresh Terraform's own state.
    """
    try:
        target = resolve_workspace(workspace)
        planned = await run_terraform(
            target,
            "plan",
            "-input=false",
            "-no-color",
            "-refresh-only",
            "-detailed-exitcode",
            f"-out={PLAN_FILE}.drift",
        )
        if planned.returncode == 1 or planned.timed_out:
            return {"ok": False, "workspace": target.name, "stage": "refresh", **planned.public()}
        shown = await run_terraform(target, "show", "-json", f"{PLAN_FILE}.drift")
        parsed = json.loads(shown.stdout) if shown.stdout else {}
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)
    except json.JSONDecodeError as exc:
        return _fail(ValueError(f"Could not parse the drift plan JSON: {exc}"))

    drifted = parsed.get("resource_drift", []) or []
    audit("detect_drift", target.name, {"drifted": len(drifted)})
    return {
        "ok": True,
        "workspace": target.name,
        "drift_detected": bool(drifted),
        "drifted_resource_count": len(drifted),
        "drifted_resources": [
            {
                "address": d.get("address"),
                "type": d.get("type"),
                "actions": (d.get("change") or {}).get("actions", []),
            }
            for d in drifted
        ],
        "interpretation": (
            "Resources listed here were changed outside Terraform. Reconcile by updating "
            "the configuration to match, or by applying to restore the declared state."
            if drifted
            else "No drift: real infrastructure matches the last known state."
        ),
    }


@mcp.tool
async def show_state(workspace: str | None = None) -> dict[str, Any]:
    """Summarise the current Terraform state, with sensitive values redacted. Read-only."""
    try:
        target = resolve_workspace(workspace)
        shown = await run_terraform(target, "show", "-json")
        parsed = json.loads(shown.stdout) if shown.stdout.strip() else {}
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)
    except json.JSONDecodeError as exc:
        return _fail(ValueError(f"Could not parse the state JSON: {exc}"))

    return {"ok": True, "workspace": target.name, **summarise_state(parsed)}


@mcp.tool
async def apply_plan(
    change_summary: dict[str, Any],
    confirmation_token: str,
    workspace: str | None = None,
) -> dict[str, Any]:
    """Apply the saved plan from :func:`plan_workspace`.

    **This changes infrastructure.** It requires ``TF_MCP_ALLOW_APPLY=true`` and a
    matching, unexpired ``confirmation_token``. Pass ``change_summary`` back exactly as
    returned by ``plan_workspace``; any modification invalidates the token.

    The saved plan file is applied, so what runs is exactly what was reviewed.
    """
    try:
        require_apply_enabled()
        target = resolve_workspace(workspace)
        verify_token(_token_payload(target.name, change_summary), confirmation_token)
        if not (target.path / PLAN_FILE).is_file():
            return {
                "ok": False,
                "error": "FileNotFoundError",
                "message": f"No saved plan in {target.name}. Run plan_workspace first.",
            }
        result = await run_terraform(target, "apply", "-input=false", "-no-color", PLAN_FILE)
    except (ApplyDisabledError, ConfirmationError, ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    audit("apply_plan", target.name, {"ok": result.ok})
    logger.warning("Applied Terraform plan in workspace %s (ok=%s)", target.name, result.ok)

    return {
        "ok": result.ok,
        "workspace": target.name,
        "next_step": (
            "Verify in the FMC GUI, then deploy to the affected devices. Re-run "
            "detect_drift afterwards to confirm the declared state holds."
        ),
        **result.public(),
    }


def _token_payload(workspace: str, summary: dict[str, Any]) -> dict[str, Any]:
    """The subset of a plan a token is bound to.

    Only the workspace and the change set matter; transient fields such as timings must
    not affect the signature.
    """
    return {
        "workspace": workspace,
        "summary": summary.get("summary"),
        "is_destructive": summary.get("is_destructive"),
        "addresses": sorted(str(change.get("address")) for change in summary.get("changes", [])),
    }


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def main() -> None:
    transport = (os.getenv("MCP_TRANSPORT") or "stdio").strip().lower()
    if transport == "http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8002"))
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
