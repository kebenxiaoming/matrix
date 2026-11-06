# -*- coding: utf-8 -*-
"""登录流程（纯 Python，不依赖 PySide6）。

四个 ``*_setup`` 内部都是**有头浏览器**（写死 ``headless=False``，不读
``MATRIX_HEADLESS``），所以扫码时窗口会直接弹出来，二维码就在窗口里。
小红书的登录走接口，没有浏览器窗口，二维码是本地生成的 PNG 文件，
通过 ``on_qrcode`` 回调交给调用方展示。

桌面端和 MCP 共用这一份实现：桌面端把二维码画进界面，MCP 用系统默认看图器打开。
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

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

    # MCP 场景下本进程是后台进程，Chrome 窗口会以最小化 + 屏幕外坐标创建，
    # 用户看不到二维码。起个短命线程把窗口摆到屏幕中央。
    try:
        from utils import window_focus

        window_focus.watch(duration=40.0)
    except Exception:
        pass

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
