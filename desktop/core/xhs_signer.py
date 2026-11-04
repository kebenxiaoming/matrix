# -*- coding: utf-8 -*-
"""小红书 x-s / x-t 签名。

原项目通过独立 Flask 服务(5005端口)算签名。客户端版本把签名做成
进程内常驻实现：复用一个浏览器实例，避免每次请求都冷启动 Chromium。

若把配置项 xhs_signer 改成 "server"，则回退到原 Flask 服务方式。
"""
from __future__ import annotations

import threading
import traceback
from pathlib import Path

from . import paths

_TLS = threading.local()
STEALTH_NAME = "cdn.jsdelivr.net_gh_requireCool_stealth.min.js_stealth.min.js"


def stealth_js_path() -> Path:
    base = Path(paths.data_root())
    candidate = base / "xhs_uploader" / STEALTH_NAME
    if candidate.exists():
        return candidate
    return paths.resource_root() / "xhs_uploader" / STEALTH_NAME


class _LocalSigner:
    """常驻 Playwright 实例的签名器。只能在其创建线程内使用。"""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._a1 = None
        self._lock = threading.RLock()

    def _ensure_page(self):
        from playwright.sync_api import sync_playwright

        if self._page is not None:
            return self._page
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True, channel="chromium")
        except Exception:
            self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context()
        js = stealth_js_path()
        if js.exists():
            self._context.add_init_script(path=str(js))
        else:
            print(f"[!] 未找到 stealth 脚本：{js}")
        self._page = self._context.new_page()
        self._page.goto("https://www.xiaohongshu.com", timeout=45000)
        self._page.wait_for_timeout(1000)
        return self._page

    def sign(self, uri, data=None, a1="", web_session="") -> dict:
        with self._lock:
            page = self._ensure_page()
            if a1 and a1 != self._a1:
                try:
                    self._context.add_cookies([
                        {"name": "a1", "value": a1, "domain": ".xiaohongshu.com", "path": "/"}
                    ])
                    page.reload(timeout=45000)
                    page.wait_for_timeout(800)
                    self._a1 = a1
                except Exception:
                    traceback.print_exc()
            result = page.evaluate(
                "([url, data]) => window._webmsxyw(url, data)", [uri, data]
            )
            return {"x-s": result["X-s"], "x-t": str(result["X-t"])}

    def close(self) -> None:
        with self._lock:
            for attr in ("_context", "_browser"):
                obj = getattr(self, attr, None)
                if obj is not None:
                    try:
                        obj.close()
                    except Exception:
                        pass
                setattr(self, attr, None)
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            self._page = None
            self._a1 = None


def _signer() -> _LocalSigner:
    signer = getattr(_TLS, "signer", None)
    if signer is None:
        signer = _LocalSigner()
        _TLS.signer = signer
    return signer


def local_sign(uri, data=None, a1="", web_session="") -> dict:
    """供 xhs_uploader 注入使用的签名函数，签名与 sign() 保持一致。"""
    last_error = None
    for _ in range(5):
        try:
            return _signer().sign(uri, data, a1 or "", web_session or "")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            traceback.print_exc()
            # 浏览器上下文可能已崩溃，重建后再试
            try:
                _signer().close()
            except Exception:
                pass
    raise RuntimeError(f"小红书签名失败：{last_error}")


def shutdown() -> None:
    signer = getattr(_TLS, "signer", None)
    if signer is not None:
        signer.close()
        _TLS.signer = None


def install(signer_mode: str = "local") -> None:
    """把签名实现注入到 xhs_uploader 模块。"""
    import xhs_uploader.main as xhs_main

    if signer_mode == "local":
        xhs_main.SIGN_FUNC = local_sign
    else:
        xhs_main.SIGN_FUNC = None  # 走原来的 Flask 签名服务
