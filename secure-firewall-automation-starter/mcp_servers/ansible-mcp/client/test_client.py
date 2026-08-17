# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Interactive smoke test for the Ansible MCP server.

python client/test_client.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import Client

from sfw_mcp_ansible.server import mcp


def show(title: str, payload: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str)[:8000])


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{prompt}{suffix}: ").strip() or default


async def call(client: Client, tool: str, **kwargs: object) -> object:
    result = await client.call_tool(tool, kwargs)
    return result.data if hasattr(result, "data") else result


async def main() -> None:
    async with Client(mcp) as client:
        listing = await call(client, "list_playbooks")
        show("list_playbooks", listing)

        if isinstance(listing, dict) and not listing.get("ok"):
            print("\nConfiguration problem - fix .env and try again.")
            return

        names = (
            [p["name"] for p in listing.get("playbooks", [])] if isinstance(listing, dict) else []
        )
        default_name = names[0] if names else ""

        menu = {
            "1": "describe_playbook",
            "2": "check_syntax",
            "3": "dry_run_playbook (--check --diff, changes nothing)",
            "q": "quit",
        }
        while True:
            print("\n" + "\n".join(f"  {k}) {v}" for k, v in menu.items()))
            choice = ask("Choose", "q")
            if choice == "q":
                return

            playbook = ask(f"Playbook {names}", default_name)
            if choice == "1":
                show("describe", await call(client, "describe_playbook", playbook=playbook))
            elif choice == "2":
                show("syntax", await call(client, "check_syntax", playbook=playbook))
            elif choice == "3":
                result = await call(client, "dry_run_playbook", playbook=playbook)
                show("dry_run", result)
                print(
                    "\nDry run only. To execute for real, review the output, then call "
                    "run_playbook_for_real with the returned plan and confirmation_token "
                    "(requires ANSIBLE_MCP_ALLOW_RUN=true)."
                )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
