# -*- coding: utf-8 -*-
"""把浏览器登录窗口推到屏幕前面。

问题：MCP server 是被客户端以后台进程方式拉起来的，它再启动 Chrome 时，
窗口会以**最小化 + 坐标在屏幕外**（实测 rect 是 -25600,-25600）的状态创建，
用户根本看不到二维码，会以为"MCP 出不了二维码"。

这里起一个短命守护线程，定期扫描浏览器窗口，把最小化或在屏幕外的窗口恢复、
移到屏幕中央并置前。只处理 Chrome 系窗口，且每个窗口只处理一次，不会和用户抢焦点。

非 Windows 平台直接返回 None，不影响原有行为。
"""
from __future__ import annotations

import sys
import threading
import time

_HANDLED: set[int] = set()
_LOCK = threading.Lock()

# Chrome 浏览器主窗口的窗口类名
_CHROME_CLASSES = {"Chrome_WidgetWin_1"}


def _log(message: str) -> None:
    try:
        from utils.login_diag import report

        report(message, "INFO")
    except Exception:
        pass


def _restore_once() -> int:
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    acted = 0

    def callback(hwnd, _lparam):
        nonlocal acted
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, buf, 128)
            if buf.value not in _CHROME_CLASSES:
                return True
            with _LOCK:
                if hwnd in _HANDLED:
                    return True

            rect = wt.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
            # 只认「坐标在屏幕外」这一种，不碰用户自己最小化的窗口：
            # 用户最小化时 rect 还停在正常坐标，只有后台进程拉起的 Chrome 才会跑到 -25600。
            if rect.left >= -10000 and rect.top >= -10000:
                with _LOCK:
                    _HANDLED.add(hwnd)
                return True

            width = max(900, min(1400, rect.right - rect.left if rect.right > rect.left else 1200))
            height = max(700, min(900, rect.bottom - rect.top if rect.bottom > rect.top else 820))
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            left = max(0, (screen_w - width) // 2)
            top = max(0, (screen_h - height) // 2)

            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.MoveWindow(hwnd, left, top, width, height, True)
            user32.SetForegroundWindow(hwnd)
            with _LOCK:
                _HANDLED.add(hwnd)
            acted += 1
        except Exception:
            return True
        return True

    user32.EnumWindows(
        ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(callback), 0
    )
    return acted


def watch(duration: float = 25.0, interval: float = 1.0) -> threading.Thread | None:
    """后台盯一段时间，把冒出来的浏览器窗口摆到屏幕中央。"""
    if not sys.platform.startswith("win"):
        return None

    def _loop() -> None:
        deadline = time.time() + duration
        fixed = 0
        while time.time() < deadline:
            try:
                if _restore_once():
                    fixed += 1
                    if fixed == 1:
                        _log("登录窗口已置前，请用手机扫码")
            except Exception:
                pass
            time.sleep(interval)

    thread = threading.Thread(target=_loop, name="login-window-focus", daemon=True)
    thread.start()
    return thread
