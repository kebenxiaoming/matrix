# -*- coding: utf-8 -*-
"""通过 MCP 客户端发起扫码登录。

用法：
    python mcp_server/_try_login.py tencent 7
    python mcp_server/_try_login.py xhs            # 新建账号
"""
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
    return "\n".join(getattr(item, "text", "") for item in (result.content or []))


async def main(platform: str | None, account_id: int | None) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            args: dict = {}
            if platform:
                args["platform"] = platform
            if account_id is not None:
                args["account_id"] = account_id
            print(f">>> matrix_login {json.dumps(args, ensure_ascii=False)}", flush=True)
            res = await session.call_tool("matrix_login", args)
            print("isError:", res.is_error)
            raw = _text(res)
            try:
                print(json.dumps(json.loads(raw), ensure_ascii=False, indent=2))
            except Exception:
                print(raw[:1500])


if __name__ == "__main__":
    plat = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    acc = int(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(plat, acc))
