# -*- coding: utf-8 -*-
"""账号登录服务：复用原项目的四个平台 setup 函数。

这些函数内部会拉起一个有界面的浏览器，由用户扫码完成登录，
成功后将 cookies(storage_state) 落盘并返回账号信息。
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import database as db
from . import paths

PLATFORM_NAMES = db.PLATFORMS


class LoginError(RuntimeError):
    """登录没有完成，消息可直接展示给用户。"""


def _import_setup(platform: int):
    """延迟导入，避免启动时就加载 playwright。"""
    if platform == 1:
        from douyin_uploader.main import douyin_setup
        return douyin_setup, True
    if platform == 2:
        from tencent_uploader.main import weixin_setup
        return weixin_setup, True
    if platform == 3:
        from xhs_uploader.main import xhs_setup
        return xhs_setup, False
    if platform == 4:
        from ks_uploader.main import ks_setup
        return ks_setup, True
    raise ValueError(f"未知平台: {platform}")


def cookie_file_for(account_row: dict, third_id: str) -> Path:
    """上传器保存 cookies 的约定路径：{目录}/{account_id}_{third_id}_account.json"""
    directory = paths.platform_account_dir(account_row["platform"])
    return directory / f"{account_row['id']}_{third_id}_account.json"


def perform_login(platform: int, account_id: int, log=print, on_qrcode=None) -> dict | None:
    """同步执行一次登录，返回 user_info；没完成则抛 LoginError。"""
    from utils import login_diag

    setup, is_async = _import_setup(platform)
    module = sys.modules.get(setup.__module__)
    if module is not None and hasattr(module, "LAST_LOGIN_ERROR"):
        module.LAST_LOGIN_ERROR = ""

    directory = str(paths.platform_account_dir(platform))
    aid = str(account_id)

    log(f"正在打开{PLATFORM_NAMES.get(platform, '')}登录页面，请在弹出的浏览器中扫码…")

    # uploader 内部的进度和异常都通过 reporter 回到界面和日志文件
    login_diag.set_reporter(lambda message, level="INFO": log(message, level))
    if on_qrcode is not None:
        login_diag.set_qrcode_handler(on_qrcode)
    try:
        if is_async:
            result = asyncio.run(setup(directory, handle=True, account_id=aid, queue_id=aid))
        else:
            result = setup(directory, handle=True, account_id=aid, queue_id=aid)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        raise LoginError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        login_diag.clear_reporter()
        login_diag.clear_qrcode_handler()

    if not result:
        reason = ""
        if module is not None:
            reason = str(getattr(module, "LAST_LOGIN_ERROR", "") or "")
        raise LoginError(reason or "扫码登录未完成或已超时")

    third_id = str(result.get("account_id") or "")
    cookie_file = cookie_file_for({"id": account_id, "platform": platform}, third_id)
    if not cookie_file.exists():
        log(f"登录信息已返回，但 cookie 文件未生成：{cookie_file}", "WARN")

    db.save_account_login(
        account_id=account_id,
        third_id=third_id,
        username=str(result.get("username") or ""),
        avatar=str(result.get("avatar") or ""),
        cookie_file=str(cookie_file),
    )
    return result


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


# ------------------------------------------------------------------ cookie 有效性

def _auth_playwright(url: str, account_file: str, failure_selector: str) -> bool:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        # channel="chromium" 走完整 Chromium 的无头模式，避免依赖 headless_shell 包
        try:
            browser = playwright.chromium.launch(headless=True, channel="chromium")
        except Exception:
            browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=account_file)
            page = context.new_page()
            page.goto(url, timeout=30000)
            try:
                page.wait_for_selector(failure_selector, timeout=5000)
                return False
            except Exception:
                return True
        finally:
            try:
                browser.close()
            except Exception:
                pass


def _douyin_cookie_valid(account_file: str) -> bool:
    """访问创作者中心后台：被弹回登录页才算失效。

    不用页面上的 class 选择器判断——抖音改版时那些名字会变，会导致明明登录着
    却被判成失效（发布被拦下）。
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, channel="chromium")
        except Exception:
            browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=account_file)
            page = context.new_page()
            page.goto("https://creator.douyin.com/creator-micro/home", timeout=30000)
            page.wait_for_timeout(3000)

            if any(token in page.url for token in ("passport", "/login")):
                return False
            try:
                qr_hint = page.get_by_text("扫码登录")
                if qr_hint.count() and qr_hint.first.is_visible():
                    return False
            except Exception:
                pass
            return True
        finally:
            try:
                browser.close()
            except Exception:
                pass


def _weixin_cookie_valid(account_file: str) -> bool:
    """视频号登录态存在 cookie 里，有会话 cookie 就当有效。

    以前这里用 ``div.title-name:has-text("视频号小店")`` 判断，那个元素早就没了，
    一旦碰巧命中就会把正常账号判成"未登录"、拦下发布。这里改为直接读文件：
    扫码成功后 storage_state 里必然有一组非空 cookie，真过期了发布时会报错。
    """
    import json

    try:
        data = json.loads(Path(account_file).read_text(encoding="utf-8"))
    except Exception:
        return False
    cookies = [c for c in (data.get("cookies") or []) if c.get("value")]
    return len(cookies) >= 1


def check_cookie(platform: int, account: dict) -> bool:
    """检查 cookie 是否仍然有效。失败（含网络异常）时返回 False。"""
    cookie_file = account.get("cookie_file") or ""
    if not cookie_file or not Path(cookie_file).exists():
        return False
    try:
        if platform == 1:
            return _douyin_cookie_valid(cookie_file)
        if platform == 2:
            return _weixin_cookie_valid(cookie_file)
        if platform == 4:
            return _auth_playwright(
                "https://cp.kuaishou.com/profile",
                cookie_file, "a.item:has-text('机构入驻')")
        if platform == 3:
            # 小红书 cookie 是纯文本串（a1=…;web_session=…），没有 web_session 就肯定不能发。
            # 真过期了打开发布页会被踢到登录页，发布流程会报明确错误。
            try:
                raw = Path(cookie_file).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return False
            for part in raw.split(";"):
                if part.strip().startswith("web_session="):
                    return len(part.split("=", 1)[1].strip()) > 10
            return False
    except Exception:
        return False
    return False
