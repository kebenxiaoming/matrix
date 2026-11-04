# -*- coding: utf-8 -*-
"""发布服务：串行消费本地任务队列，调用各平台上传器完成发布。"""
from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import config
from . import database as db
from . import paths
from .login_service import check_cookie

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


def _apply_runtime_env() -> None:
    channel = _tencent_channel()
    if channel:
        import os
        os.environ["MATRIX_TENCENT_CHANNEL"] = channel
    else:
        import os
        os.environ.pop("MATRIX_TENCENT_CHANNEL", None)


def publish_one(task: dict, log) -> tuple[int, str]:
    """执行单个任务，返回 (status, error_message)。"""
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


class PublishWorker(QThread):
    """队列消费线程。支持暂停 / 停止，停止仅作用于当前任务之后的调度。"""

    log = Signal(str, str)                 # message, level
    task_started = Signal(int)
    task_finished = Signal(int, int, str)  # task_id, status, error
    queue_idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._stop_requested = False
        self._paused = False

    # ------------------------------------------------------------------ 控制
    def stop(self) -> None:
        self._stop_requested = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------ 主循环
    def run(self) -> None:  # noqa: D102
        self._running = True
        _apply_runtime_env()
        self.log.emit("队列已启动，等待任务…", "INFO")
        idle_notified = False

        while not self._stop_requested:
            if self._paused:
                time.sleep(0.5)
                continue

            task = db.claim_next_task()
            if not task:
                if not idle_notified:
                    self.queue_idle.emit()
                    idle_notified = True
                time.sleep(max(1, int(config.get("queue_interval", 5))))
                continue

            idle_notified = False
            task_id = int(task["id"])
            self.task_started.emit(task_id)
            self.log.emit(f"取到任务 #{task_id}（{PLATFORM_NAMES.get(task['platform'], '')}）", "INFO")

            status, error = self._execute(task)
            if status == 3 and int(task.get("attempts") or 0) <= int(config.get("retry_times", 1)):
                # 首次失败按配置重试一次
                db.update_task(task_id, status=0, error=error)
                self.log.emit(f"任务 #{task_id} 失败，将在下轮自动重试：{error}", "WARN")
                self.task_finished.emit(task_id, 0, error)
            else:
                db.update_task(
                    task_id,
                    status=status,
                    error=error,
                    finished_at=int(time.time()) if status in (2, 3, 4) else 0,
                )
                db.add_log(
                    f"任务 #{task_id} {'成功' if status == 2 else '失败'}：{error or ''}".strip("："),
                    "INFO" if status == 2 else "ERROR",
                    PLATFORM_NAMES.get(task["platform"], ""),
                    task_id,
                )
                self.task_finished.emit(task_id, status, error)

            gap = int(config.get("task_gap", 30))
            for _ in range(max(0, gap)):
                if self._stop_requested:
                    break
                time.sleep(1)

        self._running = False
        self.log.emit("队列已停止", "INFO")

    def _execute(self, task: dict) -> tuple[int, str]:
        try:
            return publish_one(task, lambda msg, level="INFO": self.log.emit(msg, level))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            detail = f"{type(exc).__name__}: {exc}"
            return 3, detail
