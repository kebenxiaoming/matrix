# -*- coding: utf-8 -*-
"""把 stdout 从 MCP 协议线上摘下来。

背景：四个 uploader 里有 60 多处 print()，桌面客户端直接跑没问题（stdout 就是控制台），
但 MCP 走 stdio 传输，stdout 是 JSONRPC 专用管线，任何一行普通文本都会让客户端
「Failed to parse JSONRPC message from server」，表现为调用直接失败。

MCP SDK 自带的 stdio_server() 在 POSIX 下会把 fd 1 指向 stderr，但在 Windows 上
只改 OS 句柄、不改 CRT fd，Python 的 sys.stdout 仍然写着原来的管道，所以 print 照样
污染协议。这里在启动前自己 dup 一份真正的管线，再把 fd 1 整体改到 stderr。
"""
from __future__ import annotations

import io
import os
import sys
from typing import Any

_wire_fd: int | None = None


def detach_stdout() -> int:
    """把真正的协议管线搬到私有 fd，fd 1 全部改到 stderr。

    返回私有 fd，供 _run_stdio_on_fd 使用。
    """
    global _wire_fd
    if _wire_fd is not None:
        return _wire_fd

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass

    wire = os.dup(1)          # 私有副本，保留协议管线
    os.dup2(2, 1)             # fd 1 -> stderr，print / 子进程全部改道

    # 让 Python 层也明确指向 stderr，避免缓冲对象残留指向旧目标
    sys.stdout = sys.stderr

    _wire_fd = wire
    return wire


def _wire_stream(fd: int) -> io.TextIOWrapper:
    raw = os.fdopen(fd, "wb", buffering=0, closefd=False)
    return io.TextIOWrapper(raw, encoding="utf-8", newline="\n", write_through=True)


def run_stdio(server: Any) -> None:
    """用私有 fd 作为出口启动 MCP stdio 服务。"""
    import anyio
    from mcp.server.stdio import stdio_server

    fd = detach_stdout()
    low = getattr(server, "_lowlevel_server", None)
    if low is None:  # 版本变动兜底：退回官方入口，至少不会静默失败
        sys.stderr.write("[matrix-mcp] 取不到 lowlevel server，回退默认 stdio\n")
        server.run("stdio")
        return

    async def _serve() -> None:
        # 显式传 stdout，让 SDK 跳过它自己的 fd 1 抢占（那条路在 Windows 上不生效）
        stream = anyio.wrap_file(_wire_stream(fd))
        async with stdio_server(stdout=stream) as (read, write):
            await low.run(read, write, low.create_initialization_options())

    anyio.run(_serve)
