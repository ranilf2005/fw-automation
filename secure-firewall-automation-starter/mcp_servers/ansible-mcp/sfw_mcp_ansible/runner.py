# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Safe execution of ``ansible-playbook``.

Every invocation is a fixed argv list with ``shell=False``. Nothing supplied by the
model is ever concatenated into a command string:

* the playbook comes from the resolved allowlist, never from free text;
* extra variables are validated, then written to a temporary JSON file and passed as
  ``-e @file``, so no value can be interpreted as a flag or shell metacharacter;
* the executable is looked up once with :func:`shutil.which`;
* every run has a hard timeout and its output is size-capped and redacted.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ConfigError, Playbook, inventory_path, project_root, timeout_seconds
from .safety import redact, truncate

logger = logging.getLogger(__name__)

# Variable names an agent is allowed to set. Anything that could redirect the connection
# or inject a credential is excluded on purpose.
ALLOWED_EXTRA_VARS = frozenset(
    {
        "domain_uuid",
        "object_name",
        "object_value",
        "object_description",
        "network_objects",
        "limit",
        "offset",
        "policy_name",
    }
)

_VAR_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

# Credentials are inherited from the operator's environment, never from the agent.
PASSTHROUGH_ENV = (
    "FMC_HOST",
    "FMC_USERNAME",
    "FMC_PASSWORD",
    "FMC_DOMAIN_UUID",
    "VERIFY_SSL",
    "ANSIBLE_VAULT_PASSWORD_FILE",
    "HOME",
    "PATH",
    "LANG",
    "LC_ALL",
    "VIRTUAL_ENV",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
)


@dataclass
class RunResult:
    """Outcome of one ``ansible-playbook`` invocation."""

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
            "ok": self.ok,
            "return_code": self.returncode,
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 2),
            "stdout": truncate(redact(self.stdout)),
            "stderr": truncate(redact(self.stderr)),
        }


class ExecutableNotFound(ConfigError):
    """``ansible-playbook`` is not on PATH."""


def ansible_playbook_binary() -> str:
    binary = shutil.which("ansible-playbook")
    if not binary:
        raise ExecutableNotFound(
            "ansible-playbook is not on PATH. Install ansible-core in the environment "
            "running this MCP server: pip install 'ansible-core~=2.17'."
        )
    return binary


def validate_extra_vars(extra_vars: dict[str, Any] | None) -> dict[str, Any]:
    """Reject anything not on the allowlist, and anything structurally suspicious."""
    if not extra_vars:
        return {}
    if not isinstance(extra_vars, dict):
        raise ConfigError("extra_vars must be a JSON object.")

    clean: dict[str, Any] = {}
    for key, value in extra_vars.items():
        name = str(key).strip()
        if not _VAR_NAME.match(name):
            raise ConfigError(f"Invalid variable name {key!r}. Use lower_snake_case identifiers.")
        if name not in ALLOWED_EXTRA_VARS:
            raise ConfigError(
                f"Variable {name!r} is not permitted. Allowed variables: "
                f"{sorted(ALLOWED_EXTRA_VARS)}. Credentials and connection settings come "
                "from the server's own environment and cannot be set by a caller."
            )
        if not isinstance(value, str | int | float | bool | list | dict):
            raise ConfigError(f"Variable {name!r} has an unsupported value type.")
        clean[name] = value
    return clean


def _child_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    env["ANSIBLE_FORCE_COLOR"] = "0"
    env["ANSIBLE_NOCOLOR"] = "1"
    env["ANSIBLE_HOST_KEY_CHECKING"] = "True"
    env["PYTHONUNBUFFERED"] = "1"
    return env


async def run_playbook(
    playbook: Playbook,
    *,
    mode: str = "check",
    extra_vars: dict[str, Any] | None = None,
) -> RunResult:
    """Execute a playbook.

    ``mode`` is ``syntax`` (parse only), ``check`` (``--check --diff``, changes nothing),
    or ``run`` (real execution). Callers are responsible for gating ``run``.
    """
    if mode not in {"syntax", "check", "run"}:
        raise ConfigError(f"mode must be syntax, check, or run; got {mode!r}")

    argv = [
        ansible_playbook_binary(),
        "-i",
        str(inventory_path()),
        str(playbook.path),
    ]
    if mode == "syntax":
        argv.append("--syntax-check")
    elif mode == "check":
        argv.extend(["--check", "--diff"])

    clean_vars = validate_extra_vars(extra_vars)
    loop = asyncio.get_running_loop()
    started = loop.time()
    vars_file: str | None = None

    try:
        if clean_vars:
            # Passing values via a file keeps them out of argv and out of the process
            # table, and removes any chance of a value being read as a flag.
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8"
            ) as handle:
                json.dump(clean_vars, handle)
                vars_file = handle.name
            argv.extend(["-e", f"@{vars_file}"])

        logger.info("Running: ansible-playbook %s (mode=%s)", playbook.name, mode)
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root()),
            env=_child_env(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds()
            )
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
    finally:
        if vars_file:
            Path(vars_file).unlink(missing_ok=True)


_RECAP = re.compile(
    r"^(?P<host>\S+)\s*:\s*ok=(?P<ok>\d+)\s+changed=(?P<changed>\d+)\s+"
    r"unreachable=(?P<unreachable>\d+)\s+failed=(?P<failed>\d+)",
    re.M,
)


def parse_recap(stdout: str) -> dict[str, dict[str, int]]:
    """Extract the PLAY RECAP counters so an agent gets structure, not prose."""
    return {
        match.group("host"): {
            "ok": int(match.group("ok")),
            "changed": int(match.group("changed")),
            "unreachable": int(match.group("unreachable")),
            "failed": int(match.group("failed")),
        }
        for match in _RECAP.finditer(stdout)
    }


def changed_tasks(stdout: str) -> list[str]:
    """Task names Ansible reported as changed, in order."""
    names: list[str] = []
    current: str | None = None
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("TASK ["):
            current = stripped[6:].split("]")[0]
        elif stripped.startswith("changed:") and current and current not in names:
            names.append(current)
    return names
