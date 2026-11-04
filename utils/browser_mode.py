# -*- coding: utf-8 -*-
"""浏览器显示模式与无头反检测。

默认无头（发布时不弹浏览器窗口）；排查问题时设 MATRIX_HEADLESS=0 可切回有头。
登录流程不走这里——扫码必须让人看到窗口。

无头模式会被平台识别成自动化（抖音直接弹短信验证、视频号把发布页重定向回首页），
所以统一在这里提供 UA 伪装和少量指纹修补。
"""
import os
import sys

_FALSE_VALUES = ("0", "false", "off", "no")

# 抹掉最明显的自动化标记；对抖音这类风控能少一次人工验证
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'mimeTypes', { get: () => [1, 2, 3, 4] });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""

CHROME_ARGS = ["--disable-blink-features=AutomationControlled"]


def headless_enabled() -> bool:
    """发布用的浏览器是否无头运行。"""
    value = (os.environ.get("MATRIX_HEADLESS") or "").strip().lower()
    return value not in _FALSE_VALUES


def find_chrome_executable() -> str:
    """返回系统 Chrome 的绝对路径；找不到返回空串。

    用绝径而不是 channel="chrome"：新版 Chrome 的注册信息 Playwright 认不出来，
    会静默回退到内置 Chromium（缺 h264，视频号/小红书都传不动）。
    """
    if sys.platform.startswith("win"):
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]
        for path in candidates:
            if path and not path.startswith("%") and os.path.exists(path):
                return path
        return ""
    for path in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
                 "/opt/google/chrome/chrome"):
        if os.path.exists(path):
            return path
    return ""


def chrome_user_agent(browser_version: str) -> str:
    """按实际 Chrome 版本拼一个正常 UA（无头模式下 UA 带 HeadlessChrome）。"""
    version = (browser_version or "140.0.0.0").strip()
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{version} Safari/537.36"
    )


def context_kwargs(browser, headless: bool) -> dict:
    """无头时的上下文参数：伪装 UA + 固定视口。"""
    if not headless:
        return {}
    return {
        "user_agent": chrome_user_agent(getattr(browser, "version", "")),
        "viewport": {"width": 1440, "height": 900},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }


async def apply_stealth(context) -> None:
    """注入反自动化检测脚本（只在无头时需要）。"""
    await context.add_init_script(STEALTH_JS)
