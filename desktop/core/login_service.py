# -*- coding: utf-8 -*-
"""账号登录服务：Qt 侧封装。

登录流程本体已拆到 `login_flow.py`（纯 Python），这样 MCP server 不需要加载
PySide6 也能复用同一套扫码逻辑。这里只保留 Qt 线程包装。
"""
from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal

from . import database as db
from .auth import check_cookie  # noqa: F401  对外保持原有导入路径
from .login_flow import (  # noqa: F401  对外保持原有导出
    PLATFORM_NAMES,
    LoginError,
    cookie_file_for,
    perform_login,
)

__all__ = [
    "PLATFORM_NAMES",
    "LoginError",
    "LoginWorker",
    "check_cookie",
    "cookie_file_for",
    "perform_login",
]


class LoginWorker(QThread):
    """在后台线程执行登录，避免阻塞界面。"""

    log = Signal(str, str)          # message, level
    qrcode_ready = Signal(int, str)  # account_id, 二维码图片路径（小红书用）
    succeeded = Signal(int, dict)   # account_id, user_info
    failed = Signal(int, str)

    def __init__(self, account_id: int, platform: int, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.platform = platform

    def run(self) -> None:  # noqa: D102
        try:
            info = perform_login(
                self.platform,
                self.account_id,
                log=lambda msg, level="INFO": self.log.emit(msg, level),
                on_qrcode=lambda path: self.qrcode_ready.emit(self.account_id, path),
            )
            if info:
                self.succeeded.emit(self.account_id, info)
            else:
                self.failed.emit(self.account_id, "扫码登录未完成或已超时")
        except LoginError as exc:
            self.failed.emit(self.account_id, str(exc))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(self.account_id, f"{type(exc).__name__}: {exc}")
