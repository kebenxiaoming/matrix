# -*- coding: utf-8 -*-
"""运行环境准备与配置读取。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ensure_data_dir() -> None:
    """确定要共用哪个数据目录。

    桌面客户端打包后是绿色版，数据在 dist/视频矩阵分发/data；而 MCP 从源码运行时
    data_root 会落到项目根的 data，两者不是同一个库，MCP 会看不到已登录的账号。
    这里做一次探测，让 MCP 默认复用客户端的数据目录。
    """
    if os.environ.get("MATRIX_DATA_DIR"):
        return

    candidate = _PROJECT_ROOT / "dist" / "视频矩阵分发" / "data"
    if (candidate / "matrix.db").exists():
        os.environ["MATRIX_DATA_DIR"] = str(candidate)


def bootstrap() -> None:
    """初始化数据目录、资源文件与小红书签名器。

    等价于桌面端 main() 里启动时做的那几步，只是不涉及 Qt。
    """
    _ensure_data_dir()

    from desktop.core import paths

    paths.prepare_runtime()

    try:
        from desktop.core import config, xhs_signer

        xhs_signer.install(config.get("xhs_signer", "local") or "local")
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[matrix-mcp] 小红书签名器初始化失败：{exc}\n")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


# 单次发布最长等待时间（秒）。超时不代表失败，任务仍在队列里执行。
PUBLISH_TIMEOUT = _env_int("MATRIX_PUBLISH_TIMEOUT", 300)

# 队列中两个任务之间的间隔，避免动作过快被平台风控
TASK_GAP = _env_int("MATRIX_TASK_GAP", 15)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".flv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def allowed_roots() -> list[Path]:
    """允许发布读取的目录白名单。

    默认包含数据目录和进程工作目录；额外目录用 MATRIX_ALLOWED_DIRS 追加
    （多个路径用 os.pathsep 分隔，Windows 上是分号）。
    """
    from desktop.core import paths

    roots: list[Path] = [paths.data_root()]
    raw = os.environ.get("MATRIX_ALLOWED_DIRS", "")
    for item in raw.split(os.pathsep):
        item = item.strip()
        if not item:
            continue
        try:
            roots.append(Path(item).expanduser().resolve())
        except Exception:
            continue
    return [r for r in roots if r.exists()]


def data_dir() -> Path:
    from desktop.core import paths

    return paths.data_root()
