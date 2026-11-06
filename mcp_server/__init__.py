# -*- coding: utf-8 -*-
"""视频矩阵分发 MCP server。

独立于桌面客户端运行，复用 desktop/core 的数据层与发布逻辑（不含 PySide6）。

启动：
    python -m mcp_server
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许从任意工作目录启动：MCP 客户端的 cwd 不可控
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

__version__ = "0.1.0"
