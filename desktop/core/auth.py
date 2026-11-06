# -*- coding: utf-8 -*-
"""cookie 有效性校验（纯 Python，不依赖 PySide6）。

从 login_service 里拆出来，是因为 MCP server 需要复用这套判定，
但 MCP 进程不应该为了一个布尔判断去加载整个 Qt。

这里的原则：能读文件就不开浏览器。平台侧一改版，选择器就会失效，
误判成"未登录"会把正常账号的发布拦下来。
"""
from __future__ import annotations

import json
from pathlib import Path


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
    """先看文件有没有 cookie，再实际访问创作页看是否被踢回登录页。

    只查文件是不够的：cookie 过期后文件照旧存在，之前这套判定报"有效"，
    结果发布流程白等 60 多秒才因为找不到上传框失败。视频号失效时的表现很干净
    —— ``/platform/post/create`` 会被 302 到 ``login.html``，比任何选择器都稳。
    """
    try:
        data = json.loads(Path(account_file).read_text(encoding="utf-8"))
    except Exception:
        return False
    cookies = [c for c in (data.get("cookies") or []) if c.get("value")]
    if not cookies:
        return False

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, channel="chromium")
        except Exception:
            browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=account_file)
            page = context.new_page()
            page.goto("https://channels.weixin.qq.com/platform/post/create", timeout=30000)
            page.wait_for_timeout(1500)
            return "login" not in page.url
        finally:
            try:
                browser.close()
            except Exception:
                pass


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
