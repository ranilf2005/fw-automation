# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Safe execution of the ``terraform`` CLI, and parsing of its JSON plan output.

Every invocation is a fixed argv with ``shell=False``, run with ``-chdir`` against an
allowlisted workspace. Subcommands and flags come from this module only; nothing
supplied by a caller is ever placed on the command line.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Any

from .config import ConfigError, Workspace, timeout_seconds
from .safety import redact, truncate

logger = logging.getLogger(__name__)

# Subcommands this server is willing to run at all.
ALLOWED_SUBCOMMANDS = frozenset({"version", "init", "validate", "plan", "show", "apply"})

PASSTHROUGH_ENV = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "TF_VAR_fmc_url",
    "TF_VAR_fmc_username",
    "TF_VAR_fmc_password",
    "TF_VAR_fmc_insecure_skip_verify",
    "TF_CLI_CONFIG_FILE",
    "TF_PLUGIN_CACHE_DIR",
    "SSL_CERT_FILE",
    "TERRAFORM_BINARY",
)

PLAN_FILE = "mcp.tfplan"


class ExecutableNotFound(ConfigError):
    """``terraform`` is not on PATH."""


@dataclass
class RunResult:
    """Outcome of one ``terraform`` invocation."""

    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def public(self) -> dict[str, Any]:
        return {
            "return_code": self.returncode,
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 2),
            "stdout": truncate(redact(self.stdout)),
            "stderr": truncate(redact(self.stderr)),
        }


def terraform_binary() -> str:
    binary = os.getenv("TERRAFORM_BINARY") or shutil.which("terraform")
    if not binary or not shutil.which(binary):
        raise ExecutableNotFound(
            "terraform is not on PATH. Install Terraform >= 1.6 in the environment running "
            "this MCP server, or set TERRAFORM_BINARY to its absolute path."
        )
    return binary


def _child_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_INPUT"] = "0"
    env["CHECKPOINT_DISABLE"] = "1"
    env["NO_COLOR"] = "1"
    return env


async def run_terraform(workspace: Workspace, *args: str) -> RunResult:
    """Run ``terraform -chdir=<workspace> <args>`` with a timeout.

    ``args`` is built by this module. The first element must be an allowlisted
    subcommand; this is a defence-in-depth assertion, not the primary control.
    """
    if not args or args[0] not in ALLOWED_SUBCOMMANDS:
        raise ConfigError(f"Refusing to run terraform subcommand {args[:1]}.")

    argv = [terraform_binary(), f"-chdir={workspace.path}", *args]
    loop = asyncio.get_running_loop()
    started = loop.time()

    logger.info("Running: terraform %s in %s", " ".join(args), workspace.name)
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace.path),
        env=_child_env(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds())
    except TimeoutError:
        process.kill()
        await process.wait()
        return RunResult(
            returncode=-1,
            stdout="",
            stderr=f"Timed out after {timeout_seconds()}s and was terminated.",
            duration_seconds=loop.time() - started,
            timed_out=True,
        )

    return RunResult(
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        duration_seconds=loop.time() - started,
    )


# --------------------------------------------------------------------------------------
# Plan JSON parsing
# --------------------------------------------------------------------------------------

_ACTION_LABELS = {
    ("no-op",): "no_change",
    ("create",): "create",
    ("read",): "read",
    ("update",): "update",
    ("delete",): "delete",
    ("delete", "create"): "replace",
    ("create", "delete"): "replace",
}

SENSITIVE_PLACEHOLDER = "<sensitive>"


def classify(actions: list[str]) -> str:
    """Map Terraform's ``actions`` array onto a single human label."""
    return _ACTION_LABELS.get(tuple(actions), "+".join(actions) or "unknown")


def _sanitise(values: Any, sensitive: Any) -> Any:
    """Replace values Terraform marked sensitive before they reach a model context."""
    if isinstance(values, dict):
        marks = sensitive if isinstance(sensitive, dict) else {}
        return {
            key: SENSITIVE_PLACEHOLDER
            if marks.get(key) is True
            else _sanitise(value, marks.get(key))
            for key, value in values.items()
        }
    if isinstance(values, list):
        marks = sensitive if isinstance(sensitive, list) else []
        return [
            _sanitise(item, marks[index] if index < len(marks) else None)
            for index, item in enumerate(values)
        ]
    return SENSITIVE_PLACEHOLDER if sensitive is True else values


def summarise_plan(plan_json: dict[str, Any]) -> dict[str, Any]:
    """Turn ``terraform show -json <planfile>`` into a compact, sanitised change set."""
    changes: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for change in plan_json.get("resource_changes", []) or []:
        detail = change.get("change", {}) or {}
        actions = [str(a) for a in detail.get("actions", [])]
        label = classify(actions)
        counts[label] = counts.get(label, 0) + 1
        if label == "no_change":
            continue

        before = _sanitise(detail.get("before"), detail.get("before_sensitive"))
        after = _sanitise(detail.get("after"), detail.get("after_sensitive"))
        changes.append(
            {
                "address": change.get("address"),
                "type": change.get("type"),
                "name": change.get("name"),
                "action": label,
                "replace_reason": detail.get("action_reason") or change.get("action_reason"),
                "changed_attributes": _changed_attributes(before, after),
                "before": before,
                "after": after,
            }
        )

    return {
        "summary": {
            "create": counts.get("create", 0),
            "update": counts.get("update", 0),
            "replace": counts.get("replace", 0),
            "delete": counts.get("delete", 0),
            "no_change": counts.get("no_change", 0),
        },
        "has_changes": bool(changes),
        "is_destructive": any(c["action"] in {"delete", "replace"} for c in changes),
        "changes": changes,
        "terraform_version": plan_json.get("terraform_version"),
        "format_version": plan_json.get("format_version"),
    }


def _changed_attributes(before: Any, after: Any) -> list[str]:
    """Names of top-level attributes whose value differs."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def summarise_state(state_json: dict[str, Any]) -> dict[str, Any]:
    """Compact, sanitised view of ``terraform show -json`` for current state."""
    root = (state_json.get("values", {}) or {}).get("root_module", {}) or {}
    resources = root.get("resources", []) or []
    for module in root.get("child_modules", []) or []:
        resources.extend(module.get("resources", []) or [])

    return {
        "terraform_version": state_json.get("terraform_version"),
        "resource_count": len(resources),
        "resources": [
            {
                "address": resource.get("address"),
                "type": resource.get("type"),
                "name": resource.get("name"),
                "provider": resource.get("provider_name"),
                "values": _sanitise(resource.get("values"), resource.get("sensitive_values")),
            }
            for resource in resources
        ],
    }
