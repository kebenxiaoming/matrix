# -*- coding: utf-8 -*-
"""四个平台共用的扫码登录等待逻辑。

原实现在各平台 uploader 里用写死的元素判断登录是否完成（还有 while + 计数器
的固定轮询次数），平台一改版就永远等不到，用户只看到"未登录"。这里统一改成：
命中跳转 URL 或会话 cookie 即视为登录成功，超时给出明确原因。
"""
from __future__ import annotations

import asyncio
import time

from .login_diag import report


class LoginAborted(RuntimeError):
    """浏览器窗口被关掉，登录中断。"""


async def _cookies(context):
    try:
        return await context.cookies()
    except Exception as exc:  # noqa: BLE001
        raise LoginAborted("登录窗口被关闭了，请重新点击「去登录」") from exc


async def wait_for_login(
    context,
    page,
    *,
    url_tokens=(),
    cookie_names=(),
    success_check=None,
    timeout: int = 300,
    poll: float = 2.0,
    hint_text: str = "",
    hint_message: str = "",
) -> bool:
    """轮询等待用户完成扫码。

    命中任意一条即返回 True：会话 cookie 出现、URL 含有指定片段、
    success_check(page) 返回真值。超时返回 False。
    """
    deadline = time.time() + timeout
    hint_shown = False

    while time.time() < deadline:
        await asyncio.sleep(poll)

        cookies = await _cookies(context)
        names = {cookie.get("name") for cookie in cookies}
        if cookie_names and any(name in names for name in cookie_names):
            return True

        try:
            current_url = page.url
        except Exception as exc:  # noqa: BLE001
            raise LoginAborted("登录窗口被关闭了，请重新点击「去登录」") from exc

        if url_tokens and any(token in current_url for token in url_tokens):
            return True

        if success_check is not None:
            try:
                if await success_check(page):
                    return True
            except LoginAborted:
                raise
            except Exception:
                pass

        # 需要短信验证时提示一次，由用户自己在浏览器里完成
        if hint_text and not hint_shown:
            try:
                hint = page.get_by_text(hint_text)
                if await hint.count() and await hint.first.is_visible():
                    hint_shown = True
                    report(hint_message or f"检测到「{hint_text}」，请在浏览器窗口里完成验证", "WARN")
            except Exception:
                pass

    return False


async def grab_qrcode(page, cache_key: str, selectors, cache_data, queue_id: str = "") -> None:
    """尽力把二维码地址写进缓存（供远程前端展示），拿不到就当没这回事。"""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            await locator.wait_for(state="visible", timeout=3000)
            src = await locator.get_attribute("src")
            if src:
                cache_data(cache_key.format(queue_id=queue_id), src)
                return
        except Exception:
            continue


def pick_id_by_cookies(cookies, names) -> str:
    """从 cookie 里挑一个能当账号 ID 的值。"""
    for name in names:
        for cookie in cookies or []:
            if cookie.get("name") == name and cookie.get("value"):
                return str(cookie["value"])
    return ""
