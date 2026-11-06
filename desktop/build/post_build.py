# -*- coding: utf-8 -*-
"""打包后处理：把 Playwright 浏览器与驱动资源复制进成品目录。

之所以不在 spec 里用 datas 收集，是因为 Chromium 有 400MB+，
放进 PyInstaller 的收集流程会极慢且容易破坏目录结构。
这里直接按 Playwright 期望的布局复制：<app_root>/ms-playwright/<browser-dir>/
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist" / "视频矩阵分发"
APP_ROOT = DIST

BROWSER_SRC_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
    Path.home() / "AppData" / "Local" / "ms-playwright",
]

# 只带完整 chromium（含 headless 能力），不需要 headless_shell
KEEP_PREFIXES = ("chromium-", "ffmpeg-", "winldd-")
SKIP_PREFIXES = ("chromium_headless_shell-", "firefox-", "webkit-")


def find_browser_root() -> Path | None:
    for candidate in BROWSER_SRC_CANDIDATES:
        if candidate and candidate.exists() and any(candidate.iterdir()):
            return candidate
    return None


def copytree_fast(src: Path, dst: Path) -> None:
    """覆盖式复制：已存在则合并覆盖，不做删除（避免大批量删除文件）。"""
    shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=True)


def required_browser_dirs(src_root: Path) -> list[Path]:
    """只挑当前 Playwright 真正会用的版本，避免把历史版本一起打进去。"""
    wanted: list[Path] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            exe = Path(playwright.chromium.executable_path)
        # .../ms-playwright/chromium-1248/chrome-win64/chrome.exe
        chromium_dir = exe.parents[1]
        if chromium_dir.exists():
            wanted.append(chromium_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"    [!] 无法探测 Playwright 版本，改按最新版本挑选：{exc}")

    if not wanted:
        candidates = sorted(
            (p for p in src_root.iterdir() if p.is_dir() and p.name.startswith("chromium-")),
            key=lambda p: p.name,
        )
        if candidates:
            wanted.append(candidates[-1])

    # ffmpeg 与 winldd 各取版本号最大的一个
    for prefix in ("ffmpeg-", "winldd-"):
        candidates = sorted(
            (p for p in src_root.iterdir() if p.is_dir() and p.name.startswith(prefix)),
            key=lambda p: p.name,
        )
        if candidates:
            wanted.append(candidates[-1])
    return wanted


def main() -> int:
    if not DIST.exists():
        print(f"[x] 未找到打包输出目录：{DIST}")
        print("    请先执行：python -m PyInstaller desktop/build/matrix_client.spec --noconfirm")
        return 1

    exe = DIST / "视频矩阵分发.exe"
    print(f"[1/4] 检查可执行文件… {exe.exists()} {exe}")

    src_root = find_browser_root()
    if src_root is None:
        print("[x] 未找到 Playwright 浏览器目录，请先执行：python -m playwright install chromium")
        return 1

    target_root = APP_ROOT / "ms-playwright"
    target_root.mkdir(parents=True, exist_ok=True)

    print(f"[2/4] 复制浏览器资源：{src_root} -> {target_root}")
    copied = []
    for item in required_browser_dirs(src_root):
        started = time.time()
        copytree_fast(item, target_root / item.name)
        size = sum(f.stat().st_size for f in (target_root / item.name).rglob("*") if f.is_file())
        copied.append((item.name, size, time.time() - started))
        print(f"    - {item.name}  {size / 1e6:.0f}MB  {time.time() - started:.1f}s")

    if not copied:
        print("[x] 没有复制任何浏览器，请检查 ms-playwright 目录内容")
        return 1

    print("[3/4] 校验资源文件…")
    checks = {
        "内置签名脚本": DIST / "_internal" / "xhs_uploader" / "cdn.jsdelivr.net_gh_requireCool_stealth.min.js_stealth.min.js",
        "Qt 平台插件": DIST / "_internal" / "PySide6" / "plugins" / "platforms" / "qwindows.dll",
    }
    ok = True
    for name, path in checks.items():
        exists = path.exists()
        ok = ok and exists
        print(f"    {'✓' if exists else '✗'} {name}: {path}")

    chrome_exes = list(target_root.glob("chromium-*/chrome-win64/chrome.exe"))
    if chrome_exes:
        print(f"    ✓ Chromium 主程序: {chrome_exes[0]}")
    else:
        ok = False
        print("    ✗ 未找到 chrome.exe")

    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"[4/4] 成品目录：{DIST}")
    print(f"      总大小：{total / 1e6:.0f} MB")
    print("      完成" if ok else "      存在缺失项，请检查上面的 ✗")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
