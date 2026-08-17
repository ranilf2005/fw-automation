# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Interactive smoke test for the Secure Firewall REST API MCP server.

Runs the server in-process over stdio and drives its tools from a menu, so you can
confirm connectivity and permissions before wiring the server into an AI agent.

    python client/test_client.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import Client

from sfw_mcp_rest.server import mcp


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
        tools = await client.list_tools()
        print("Connected. Tools available:")
        for tool in tools:
            print(f"  - {tool.name}")

        profiles = await call(client, "list_fmc_profiles")
        show("list_fmc_profiles", profiles)

        if isinstance(profiles, dict) and not profiles.get("ok"):
            print("\nConfiguration problem - fix .env and try again.")
            return

        profile = ask("FMC profile id or alias (blank for default)")

        menu = {
            "1": "get_inventory",
            "2": "search_objects",
            "3": "find_object_usage",
            "4": "list_access_rules",
            "5": "get_deployment_status",
            "6": "preview_object_changes",
            "q": "quit",
        }
        while True:
            print("\n" + "\n".join(f"  {k}) {v}" for k, v in menu.items()))
            choice = ask("Choose", "q")
            if choice == "q":
                return

            if choice == "1":
                show("inventory", await call(client, "get_inventory", fmc_profile=profile))
            elif choice == "2":
                indicator = ask("Indicator (name, IP, CIDR, or FQDN)", "10.10.20.5")
                kind = ask("Type (any/host/network/service)", "any")
                show(
                    "search_objects",
                    await call(
                        client,
                        "search_objects",
                        indicator=indicator,
                        object_type=kind,
                        fmc_profile=profile,
                    ),
                )
            elif choice == "3":
                show(
                    "find_object_usage",
                    await call(
                        client,
                        "find_object_usage",
                        object_name=ask("Object name", "APP1_HOST"),
                        access_policy=ask("Access policy name or id"),
                        fmc_profile=profile,
                    ),
                )
            elif choice == "4":
                show(
                    "list_access_rules",
                    await call(
                        client,
                        "list_access_rules",
                        access_policy=ask("Access policy name or id"),
                        action=ask("Action filter (blank for all)") or None,
                        fmc_profile=profile,
                    ),
                )
            elif choice == "5":
                show(
                    "get_deployment_status",
                    await call(client, "get_deployment_status", fmc_profile=profile),
                )
            elif choice == "6":
                sample = [
                    {
                        "name": ask("Object name", "MCP_TEST_NET"),
                        "type": ask("Type (Host/Network)", "Network"),
                        "value": ask("Value", "10.99.99.0/24"),
                        "description": "Created from the MCP test client",
                    }
                ]
                show(
                    "preview_object_changes",
                    await call(
                        client,
                        "preview_object_changes",
                        objects=sample,
                        fmc_profile=profile,
                    ),
                )
                print(
                    "\nPreview only. To apply, review the plan, then call "
                    "apply_object_changes with the plan and confirmation_token "
                    "(requires FMC_ALLOW_WRITES=true)."
                )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
