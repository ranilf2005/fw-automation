# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Interactive smoke test for the Terraform MCP server.

python client/test_client.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import Client

from sfw_mcp_terraform.server import mcp


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
        listing = await call(client, "list_workspaces")
        show("list_workspaces", listing)

        if isinstance(listing, dict) and not listing.get("ok"):
            print("\nConfiguration problem - fix .env and try again.")
            return

        names = (
            [w["name"] for w in listing.get("workspaces", [])] if isinstance(listing, dict) else []
        )
        default_name = names[0] if names else ""

        menu = {
            "1": "get_versions",
            "2": "init_workspace (-backend=false)",
            "3": "validate_workspace",
            "4": "plan_workspace",
            "5": "explain_plan",
            "6": "detect_drift",
            "7": "show_state",
            "q": "quit",
        }
        tools = {
            "1": "get_versions",
            "2": "init_workspace",
            "3": "validate_workspace",
            "4": "plan_workspace",
            "5": "explain_plan",
            "6": "detect_drift",
            "7": "show_state",
        }
        while True:
            print("\n" + "\n".join(f"  {k}) {v}" for k, v in menu.items()))
            choice = ask("Choose", "q")
            if choice == "q":
                return
            if choice not in tools:
                continue

            workspace = ask(f"Workspace {names}", default_name)
            result = await call(client, tools[choice], workspace=workspace)
            show(tools[choice], result)

            if choice == "4" and isinstance(result, dict) and result.get("is_destructive"):
                print(
                    "\n*** This plan DELETES or REPLACES resources. ***\n"
                    "Review every address above before considering apply_plan "
                    "(requires TF_MCP_ALLOW_APPLY=true)."
                )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
