# -*- coding: utf-8 -*-
"""入口：python -m mcp_server

MCP 客户端通过 stdio 拉起本进程，因此 stdout 只能输出协议数据，
所有诊断信息一律走 stderr 或日志文件。
"""
from __future__ import annotations

import sys

from . import settings


def main() -> int:
    settings.bootstrap()

    from .lock import InstanceLock
    from .server import server

    lock = InstanceLock(settings.data_dir() / ".mcp.lock")
    if not lock.acquire():
        sys.stderr.write(
            "[matrix-mcp] 已有另一个 MCP 实例在运行（.mcp.lock 被占用）。\n"
            "[matrix-mcp] 请先关闭其他客户端里的 matrix-publisher，或结束残留进程。\n"
        )
        return 1

    try:
        # 必须在 bootstrap 之后、服务启动之前改道：bootstrap 里也可能有 print
        from .stdio_guard import detach_stdout, run_stdio

        detach_stdout()
        sys.stderr.write("[matrix-mcp] 已启动，等待客户端调用…\n")
        run_stdio(server)
    except KeyboardInterrupt:
        pass
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
