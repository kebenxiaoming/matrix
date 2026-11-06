# -*- coding: utf-8 -*-
"""真实发布试用：以 MCP 客户端身份走完整链路（dry_run -> 真实发布）。

用法：
    python mcp_server/_try_publish.py tencent 7
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
    parts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _show(label: str, res) -> dict:
    print(f"\n== {label} ==")
    print("isError:", res.is_error)
    raw = _text(res)
    try:
        data = json.loads(raw)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data
    except Exception:
        print(raw[:1500])
        return {}


async def main(platform: str, account_id: int, video: str) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            _show("matrix_check_login", await session.call_tool(
                "matrix_check_login", {"account_id": account_id}))

            _show("dry_run", await session.call_tool("matrix_publish", {
                "platform": platform,
                "account_id": account_id,
                "video_path": video,
                "title": "MCP 接口自检",
                "tags": ["测试"],
                "dry_run": True,
            }))

            print("\n>>> 开始真实发布，预计 20-40 秒 ...", flush=True)
            data = _show("real publish", await session.call_tool("matrix_publish", {
                "platform": platform,
                "account_id": account_id,
                "video_path": video,
                "title": "MCP 接口自检",
                "tags": ["测试"],
                "dry_run": False,
                "timeout": 240,
            }))
            print("\n>>> task_id =", data.get("task_id"))


if __name__ == "__main__":
    plat = sys.argv[1] if len(sys.argv) > 1 else "tencent"
    acc = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    vid = sys.argv[3] if len(sys.argv) > 3 else str(
        ROOT / "dist" / "视频矩阵分发" / "data" / "_mcp_test.mp4")
    asyncio.run(main(plat, acc, vid))
