# -*- coding: utf-8 -*-
"""发布服务：串行消费本地任务队列，调用各平台上传器完成发布。

单任务执行逻辑在 `publisher.py`（纯 Python），这里只负责 Qt 线程与队列调度。
"""
from __future__ import annotations

import time
import traceback

from PySide6.QtCore import QThread, Signal

from . import config
from . import database as db
from .publisher import (  # noqa: F401  对外保持原有导入路径
    PLATFORM_NAMES,
    apply_runtime_env as _apply_runtime_env,
    parse_publish_time,
    publish_one,
    split_tags,
)


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
