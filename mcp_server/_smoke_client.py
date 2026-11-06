# -*- coding: utf-8 -*-
"""本地联调：以真实 MCP 客户端拉起 server，验证握手、工具清单与两次调用。"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client


def _text(result) -> str:
    parts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print("== initialize ==")
            print("server:", info.server_info.name, info.server_info.version)

            tools = await session.list_tools()
            print("\n== tools ==")
            for tool in tools.tools:
                print(f"  - {tool.name}")

            print("\n== matrix_list_platforms ==")
            res = await session.call_tool("matrix_list_platforms", {})
            print("isError:", res.is_error)
            print(_text(res)[:600])

            print("\n== matrix_health ==")
            res = await session.call_tool("matrix_health", {})
            print("isError:", res.is_error)
            print(_text(res)[:900])

            print("\n== matrix_list_accounts ==")
            res = await session.call_tool("matrix_list_accounts", {})
            print("isError:", res.is_error)
            print(_text(res)[:600])


if __name__ == "__main__":
    asyncio.run(main())
