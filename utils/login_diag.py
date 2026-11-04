# -*- coding: utf-8 -*-
"""登录过程诊断：把进度与失败原因回显到桌面界面，并落一份文件日志。

原项目的 uploader 内部是 ``except: traceback.print_exc()``，打包成无控制台的
窗口程序后这些信息全部丢失，用户只能看到"未登录"却不知道为什么。
桌面端在调用登录前通过 :func:`set_reporter` 注入回调，uploader 里统一调
:func:`report`，失败原因就能一路传到界面和日志文件。
"""
from __future__ import annotations

import time
import traceback
from pathlib import Path

_reporter = None
_qrcode_handler = None


def set_reporter(fn) -> None:
    """注入日志回调，签名为 fn(message: str, level: str)。"""
    global _reporter
    _reporter = fn


def clear_reporter() -> None:
    global _reporter
    _reporter = None


def set_qrcode_handler(fn) -> None:
    """注入二维码展示回调，签名为 fn(image_path: str)。

    小红书的登录是纯接口扫码，没有浏览器窗口，必须把二维码交给界面显示。
    """
    global _qrcode_handler
    _qrcode_handler = fn


def clear_qrcode_handler() -> None:
    global _qrcode_handler
    _qrcode_handler = None


def publish_qrcode(image_path) -> None:
    """把二维码路径交给界面；没有注入回调时退回系统看图工具。"""
    path = str(image_path)
    if _qrcode_handler is not None:
        try:
            _qrcode_handler(path)
            return
        except Exception:
            pass
    try:
        import os

        os.startfile(path)  # noqa: S606 - Windows 下用默认看图程序打开
    except Exception:
        report(f"二维码已生成，请手动打开：{path}", "WARN")


def report(message: str, level: str = "INFO") -> None:
    """输出一条进度日志：文件 + 界面（或 stdout）。"""
    try:
        _write(f"[{time.strftime('%H:%M:%S')}] [{level}] {message}")
    except Exception:
        pass
    if _reporter is not None:
        try:
            _reporter(message, level)
            return
        except Exception:
            pass
    print(f"[{level}] {message}", flush=True)


def report_exc(message: str, exc: BaseException | None = None) -> None:
    """输出异常：界面只给一行摘要，文件里保留完整堆栈。"""
    if exc is not None:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        summary = f"{type(exc).__name__}: {exc}"
    else:
        detail = traceback.format_exc()
        lines = [line for line in detail.strip().splitlines() if line.strip()]
        summary = lines[-1] if lines else "未知错误"
    report(f"{message}：{summary}", "ERROR")
    try:
        _write(detail)
    except Exception:
        pass


def _log_path() -> Path:
    try:
        from desktop.core import paths

        return paths.logs_dir() / "uploader.log"
    except Exception:
        return Path(__file__).resolve().parent.parent / "logs" / "uploader.log"


def _write(text: str) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")
