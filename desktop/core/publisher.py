# -*- coding: utf-8 -*-
"""单任务发布执行器（纯 Python，不依赖 PySide6）。

从 publish_service 里拆出来，让 MCP server 可以在不加载 Qt 的进程里复用
完全相同的发布逻辑——否则桌面端和 MCP 两套实现迟早会跑偏。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from . import config
from . import database as db
from .auth import check_cookie

PLATFORM_NAMES = db.PLATFORMS


def parse_publish_time(value: str):
    """把界面上的定时字符串解析成 datetime；空值返回 None 表示立即发布。"""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def split_tags(tag_str: str) -> list[str]:
    if not tag_str:
        return []
    raw = tag_str.replace("，", " ").replace(",", " ").replace("#", " ")
    return [item for item in raw.split() if item]


def _tencent_channel() -> str:
    value = (config.get("tencent_channel") or "").strip()
    return value


def apply_runtime_env() -> None:
    """把配置里的视频号浏览器通道同步到环境变量，上传器启动时读取。"""
    import os

    channel = _tencent_channel()
    if channel:
        os.environ["MATRIX_TENCENT_CHANNEL"] = channel
    else:
        os.environ.pop("MATRIX_TENCENT_CHANNEL", None)


def publish_one(task: dict, log) -> tuple[int, str]:
    """执行单个任务，返回 (status, error_message)。

    status 语义与桌面端一致：2 成功、3 失败、4 登录失效。
    """
    platform = int(task["platform"])
    account = db.get_account(int(task["account_id"]))
    name = PLATFORM_NAMES.get(platform, f"平台{platform}")

    if not account:
        return 3, "账号不存在（可能已被删除）"

    video_path = Path(task["video_path"])
    cover_path = Path(task["cover_path"]) if task.get("cover_path") else None
    if not video_path.exists():
        return 3, f"视频文件不存在：{video_path}"

    cookie_file = account.get("cookie_file") or ""
    if not cookie_file or not Path(cookie_file).exists():
        return 4, "登录信息缺失，请重新登录该账号"

    log(f"正在校验 {name} 账号「{account['username'] or account['third_id']}」登录状态…")
    if not check_cookie(platform, account):
        db.mark_account_status(int(account["id"]), 2)
        return 4, "登录已失效，请在账号页重新扫码登录"

    title = task["title"] or video_path.stem
    tags = split_tags(task["tags"])
    location = task["location"] or config.get("default_location") or ""
    publish_dt = parse_publish_time(task["publish_at"])
    description = task.get("description") or ""

    log(f"[{name}] 开始发布：{title}")

    if platform == 1:
        from douyin_uploader.main import DouYinVideo

        app = DouYinVideo(
            title, str(video_path), str(cover_path or ""), tags,
            publish_dt or 0, cookie_file, location, description,
        )
        asyncio.run(app.main())
    elif platform == 2:
        from tencent_uploader.main import TencentVideo

        app = TencentVideo(
            title, str(video_path), str(cover_path or ""), tags,
            publish_dt or 0, cookie_file, location,
        )
        asyncio.run(app.main())
    elif platform == 3:
        from xhs_uploader.main import upload_xhs_video
        from . import xhs_signer

        # 兜底：不论从哪个入口进发布，都确保进程内签名器已注入（否则会去连 Flask 服务）
        xhs_signer.install(config.get("xhs_signer", "local") or "local")

        ok = upload_xhs_video(
            title, str(video_path), tags, publish_dt,
            description, str(cover_path or ""), cookie_file,
        )
        if not ok:
            return 3, "小红书发布失败，请查看日志"
    elif platform == 4:
        from ks_uploader.main import KuaiShouVideo

        app = KuaiShouVideo(
            title, str(video_path), str(cover_path or ""), tags,
            publish_dt or 0, cookie_file, location, description,
        )
        asyncio.run(app.main())
    else:
        return 3, f"不支持的平台类型：{platform}"

    log(f"[{name}] 发布成功：{title}")
    return 2, ""
