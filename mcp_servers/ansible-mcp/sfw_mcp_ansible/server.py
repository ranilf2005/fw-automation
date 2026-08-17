# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""MCP server that lets an AI agent run reviewed Ansible playbooks against FMC.

The agent never writes automation. It selects from an allowlist of playbooks a human
already reviewed and supplies validated variables, so the audit story stays intact: what
ran is still the playbook in version control.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import yaml
from fastmcp import FastMCP

from .config import (
    ConfigError,
    discover_playbooks,
    inventory_path,
    playbook_dir,
    project_root,
    resolve_playbook,
    run_enabled,
    timeout_seconds,
)
from .runner import (
    ALLOWED_EXTRA_VARS,
    ExecutableNotFound,
    changed_tasks,
    parse_recap,
    run_playbook,
    validate_extra_vars,
)
from .safety import (
    ConfirmationError,
    RunsDisabledError,
    audit,
    issue_token,
    redact,
    require_runs_enabled,
    verify_token,
)

logging.basicConfig(
    stream=sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sfw_mcp_ansible")

mcp: FastMCP = FastMCP(
    name="cisco-secure-firewall-ansible",
    instructions=(
        "Runs reviewed Ansible playbooks against Cisco Secure Firewall Management Center. "
        "Call list_playbooks first. You may always check_syntax and dry_run_playbook. "
        "To actually change anything you must dry_run_playbook, show the result to the "
        "user, then call run_playbook with the returned confirmation token."
    ),
)


def _fail(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": type(exc).__name__, "message": redact(str(exc))}


@mcp.tool
async def list_playbooks() -> dict[str, Any]:
    """List the playbooks this server is allowed to run.

    Always call this first. ``mutates_configuration`` tells you whether a playbook
    changes FMC state; those require the dry-run and confirmation flow.
    """
    try:
        playbooks = discover_playbooks()
        return {
            "ok": True,
            "project_root": str(project_root()),
            "playbook_dir": str(playbook_dir()),
            "inventory": str(inventory_path()),
            "real_runs_enabled": run_enabled(),
            "timeout_seconds": timeout_seconds(),
            "allowed_extra_vars": sorted(ALLOWED_EXTRA_VARS),
            "playbooks": [p.public() for p in playbooks.values()],
        }
    except ConfigError as exc:
        return _fail(exc)


@mcp.tool
async def describe_playbook(playbook: str) -> dict[str, Any]:
    """Show a playbook's plays, task names, and declared variables without running it.

    Read-only. Use this to explain to a user what a run would do.
    """
    try:
        entry = resolve_playbook(playbook)
        parsed = yaml.safe_load(entry.path.read_text(encoding="utf-8"))
    except (ConfigError, OSError, yaml.YAMLError) as exc:
        return _fail(exc)

    plays: list[dict[str, Any]] = []
    for play in parsed if isinstance(parsed, list) else []:
        if not isinstance(play, dict):
            continue
        plays.append(
            {
                "name": play.get("name"),
                "hosts": play.get("hosts"),
                "connection": play.get("connection"),
                "vars_files": play.get("vars_files", []),
                "tasks": [
                    {
                        "name": task.get("name"),
                        "module": next(
                            (
                                key
                                for key in task
                                if key not in {"name", "vars", "when", "register", "no_log", "loop"}
                            ),
                            None,
                        ),
                        "secrets_hidden": bool(task.get("no_log")),
                    }
                    for task in play.get("tasks", [])
                    if isinstance(task, dict)
                ],
            }
        )

    return {
        "ok": True,
        "playbook": entry.name,
        "description": entry.description,
        "mutates_configuration": entry.mutates,
        "path": str(entry.path),
        "plays": plays,
    }


@mcp.tool
async def check_syntax(playbook: str) -> dict[str, Any]:
    """Parse a playbook with ``ansible-playbook --syntax-check``. Connects to nothing.

    Read-only and completely safe. Use it to validate before a dry run.
    """
    try:
        entry = resolve_playbook(playbook)
        result = await run_playbook(entry, mode="syntax")
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    audit("check_syntax", entry.name, {"ok": result.ok})
    return {"ok": True, "playbook": entry.name, "syntax_valid": result.ok, **result.public()}


@mcp.tool
async def dry_run_playbook(
    playbook: str,
    extra_vars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a playbook with ``--check --diff``: report what would change, change nothing.

    Returns the PLAY RECAP counters, the list of tasks that would change, and a
    ``confirmation_token`` to pass to :func:`run_playbook`.

    Note that ``--check`` fidelity depends on the modules involved; treat the result as a
    strong indication, not a guarantee. Always validate against a lab first.
    """
    try:
        entry = resolve_playbook(playbook)
        clean_vars = validate_extra_vars(extra_vars)
        result = await run_playbook(entry, mode="check", extra_vars=clean_vars)
    except (ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    recap = parse_recap(result.stdout)
    would_change = changed_tasks(result.stdout)
    plan = {"playbook": entry.name, "extra_vars": clean_vars, "would_change": would_change}
    audit("dry_run_playbook", entry.name, {"would_change": len(would_change)})

    response: dict[str, Any] = {
        "ok": True,
        "playbook": entry.name,
        "mode": "check",
        "recap": recap,
        "would_change_task_count": len(would_change),
        "would_change_tasks": would_change,
        "plan": plan,
        "real_runs_enabled": run_enabled(),
        **result.public(),
    }
    response.update(issue_token(plan))
    return response


@mcp.tool
async def run_playbook_for_real(
    plan: dict[str, Any],
    confirmation_token: str,
) -> dict[str, Any]:
    """Execute a playbook for real, using a plan from :func:`dry_run_playbook`.

    **This changes FMC configuration.** It requires ``ANSIBLE_MCP_ALLOW_RUN=true`` and a
    matching, unexpired ``confirmation_token``. Pass ``plan`` back exactly as returned;
    any modification invalidates the token.
    """
    try:
        require_runs_enabled()
        verify_token(plan, confirmation_token)
        entry = resolve_playbook(str(plan.get("playbook", "")))
        clean_vars = validate_extra_vars(plan.get("extra_vars"))
        result = await run_playbook(entry, mode="run", extra_vars=clean_vars)
    except (RunsDisabledError, ConfirmationError, ConfigError, ExecutableNotFound) as exc:
        return _fail(exc)

    recap = parse_recap(result.stdout)
    changed = changed_tasks(result.stdout)
    audit("run_playbook_for_real", entry.name, {"changed": len(changed), "ok": result.ok})
    logger.warning("Executed playbook %s for real (ok=%s)", entry.name, result.ok)

    return {
        "ok": True,
        "playbook": entry.name,
        "mode": "run",
        "recap": recap,
        "changed_task_count": len(changed),
        "changed_tasks": changed,
        "next_step": (
            "Verify in the FMC GUI, then deploy to the affected devices. This server does "
            "not trigger deployments."
        ),
        **result.public(),
    }


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def main() -> None:
    transport = (os.getenv("MCP_TRANSPORT") or "stdio").strip().lower()
    if transport == "http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8001"))
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
