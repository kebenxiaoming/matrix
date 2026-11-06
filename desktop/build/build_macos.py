# -*- coding: utf-8 -*-
"""macOS 一键构建：图标 → PyInstaller(.app) → 内置浏览器 → 签名 → dmg。

必须在 macOS 上执行（PyInstaller 不支持交叉编译）：

    python3 desktop/build/build_macos.py                 # 完整构建
    python3 desktop/build/build_macos.py --skip-deps     # 依赖已装好
    python3 desktop/build/build_macos.py --no-dmg        # 只要 .app

产物：
    dist_mac/视频矩阵分发.app
    dist_mac/视频矩阵分发-<arch>.dmg
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "desktop" / "build"
RESOURCES = ROOT / "desktop" / "resources"
SPEC = BUILD / "matrix_client_macos.spec"
DIST = ROOT / "dist_mac"
WORK = ROOT / "build_tmp" / "mac"
APP_NAME = "视频矩阵分发"
APP = DIST / f"{APP_NAME}.app"

# Playwright 在 macOS 上的默认缓存位置（顺带兼容其他系统，便于本机调试脚本逻辑）
if sys.platform == "darwin":
    PLAYWRIGHT_CACHE = Path.home() / "Library" / "Caches" / "ms-playwright"
else:
    _local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    PLAYWRIGHT_CACHE = Path(_local) / "ms-playwright"


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], title: str, check: bool = True) -> subprocess.CompletedProcess:
    log(f"\n=== {title} ===")
    log("  " + " ".join(str(c) for c in cmd))
    started = time.time()
    result = subprocess.run([str(c) for c in cmd], cwd=str(ROOT))
    elapsed = time.time() - started
    if check and result.returncode != 0:
        log(f"[x] 失败（退出码 {result.returncode}，用时 {elapsed:.1f}s）")
        sys.exit(result.returncode)
    log(f"  完成，用时 {elapsed:.1f}s")
    return result


def ensure_dependencies() -> None:
    missing = []
    for module in ("PySide6", "playwright", "PyInstaller", "PIL", "lxml", "xhs", "qrcode"):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001
            missing.append(module)
    if not missing:
        log("[1/7] 依赖齐全")
        return
    log(f"[1/7] 缺少依赖：{', '.join(missing)}，开始安装…")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements-desktop.txt"], "安装依赖")


def ensure_chromium() -> Path:
    """确保本机有 Playwright 的 chromium，返回其根目录。"""
    run([sys.executable, "-m", "playwright", "install", "chromium"], "[2/7] 安装 Chromium")

    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or PLAYWRIGHT_CACHE)
    if not root.exists():
        log(f"[x] 未找到浏览器目录：{root}")
        sys.exit(1)
    return root


def make_icns(force: bool = False) -> Path:
    """用 Qt 画一张 1024 源图，再交给 iconutil 打成 icns。"""
    icns = RESOURCES / "app.icns"
    if icns.exists() and not force:
        log(f"[3/7] 图标已存在：{icns.name}")
        return icns

    log("[3/7] 生成 macOS 图标…")
    # 无头环境下 QPixmap 需要 offscreen 平台插件
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    tmp = Path(tempfile.mkdtemp(prefix="matrix_icon_"))
    try:
        source_png = tmp / "icon_1024.png"
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance() or QApplication([])
            from desktop.ui.icon import _draw_pixmap

            _draw_pixmap(1024).save(str(source_png), "PNG")
            if app is not None:
                app.quit()
        except Exception as exc:  # noqa: BLE001
            # CI 或极端环境下 Qt 起不来时，退化到放大已有的 .ico
            log(f"    [!] Qt 绘制失败，改用 app.ico 放大：{exc}")
            from PIL import Image

            ico = RESOURCES / "app.ico"
            if not ico.exists():
                log("[x] 既无法绘制，也没有 app.ico，无法生成图标")
                sys.exit(1)
            image = Image.open(ico)
            image = image.resize((1024, 1024), Image.LANCZOS)
            image.save(source_png)

        from PIL import Image

        base = Image.open(source_png).convert("RGBA")
        iconset = tmp / "AppIcon.iconset"
        iconset.mkdir()
        variants = [
            (16, "icon_16x16"), (32, "icon_16x16@2x"),
            (32, "icon_32x32"), (64, "icon_32x32@2x"),
            (128, "icon_128x128"), (256, "icon_128x128@2x"),
            (256, "icon_256x256"), (512, "icon_256x256@2x"),
            (512, "icon_512x512"), (1024, "icon_512x512@2x"),
        ]
        for size, name in variants:
            base.resize((size, size), Image.LANCZOS).save(iconset / f"{name}.png")

        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            log(f"[x] iconutil 失败：{result.stderr.strip()}")
            sys.exit(1)
        log(f"  已生成 {icns.name}（{icns.stat().st_size // 1024} KB）")
        return icns
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_app(version: str) -> None:
    if DIST.exists():
        stamp = time.strftime("%H%M%S")
        archived = ROOT / f"dist_mac_old_{stamp}"
        DIST.rename(archived)
        log(f"  已归档旧构建 -> {archived.name}")

    env = os.environ.copy()
    env["MATRIX_VERSION"] = version
    log("\n=== [4/7] PyInstaller 打包 ===")
    log(f"  {sys.executable} -m PyInstaller {SPEC}")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC),
         "--noconfirm", "--distpath", str(DIST), "--workpath", str(WORK)],
        cwd=str(ROOT), env=env,
    )
    if result.returncode != 0:
        log(f"[x] PyInstaller 失败（退出码 {result.returncode}）")
        sys.exit(result.returncode)
    if not APP.exists():
        log(f"[x] 未生成 {APP}")
        sys.exit(1)


def _required_browser_dirs(src_root: Path) -> list[Path]:
    """只带当前 Playwright 真正会用的版本，跳过 headless_shell 和 firefox/webkit。"""
    wanted: list[Path] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            exe = Path(playwright.chromium.executable_path)
        # .../ms-playwright/chromium-1148/chrome-mac/Chromium.app/...
        for parent in exe.parents:
            if parent.parent == src_root:
                wanted.append(parent)
                break
    except Exception as exc:  # noqa: BLE001
        log(f"    [!] 无法探测 Playwright 版本，改按最新版本挑选：{exc}")

    if not wanted:
        candidates = sorted(
            (p for p in src_root.iterdir() if p.is_dir() and p.name.startswith("chromium-")),
            key=lambda p: p.name,
        )
        if candidates:
            wanted.append(candidates[-1])

    for prefix in ("ffmpeg-",):
        candidates = sorted(
            (p for p in src_root.iterdir() if p.is_dir() and p.name.startswith(prefix)),
            key=lambda p: p.name,
        )
        if candidates:
            wanted.append(candidates[-1])
    return wanted


def bundle_browsers(src_root: Path) -> None:
    target_root = APP / "Contents" / "Resources" / "ms-playwright"
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True)

    # 兜底：PyInstaller 6 在不同版本里会把 datas 放进 Resources 或 Frameworks，
    # 统一再拷一份到 Contents/Resources，运行时按 xhs_uploader 是否存在来定位。
    xhs_src = RESOURCES / "xhs_uploader"
    if xhs_src.exists():
        shutil.copytree(xhs_src, APP / "Contents" / "Resources" / "xhs_uploader",
                        symlinks=True, dirs_exist_ok=True)

    dirs = _required_browser_dirs(src_root)
    if not dirs:
        log("[x] 没有找到可打包的 chromium，请先执行 python -m playwright install chromium")
        sys.exit(1)

    log(f"\n=== [5/7] 内置浏览器 -> {target_root.relative_to(APP)} ===")
    for item in dirs:
        started = time.time()
        shutil.copytree(item, target_root / item.name, symlinks=True, dirs_exist_ok=True)
        size = sum(f.stat().st_size for f in (target_root / item.name).rglob("*") if f.is_file())
        log(f"  - {item.name}  {size / 1e6:.0f}MB  {time.time() - started:.1f}s")

    # Chromium.app 依赖可执行权限，某些文件系统/压缩方式会丢，统一补一遍
    for exe_name in ("Chromium", "chrome", "chrome_crashpad_handler"):
        for exe in target_root.rglob(exe_name):
            if exe.is_file():
                try:
                    exe.chmod(exe.stat().st_mode | 0o755)
                except Exception:
                    pass


def sign_app(identity: str, deep: bool) -> None:
    log(f"\n=== [6/7] 代码签名（{identity or 'ad-hoc'}）===")
    if identity:
        cmd = ["codesign", "--force", "--timestamp", "--options", "runtime",
               "--sign", identity]
    else:
        cmd = ["codesign", "--force", "--sign", "-"]
    if deep:
        cmd.append("--deep")
    cmd.append(str(APP))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  [!] 签名失败：{result.stderr.strip()}")
        log("      仍可生成 dmg，但目标机器需要手动解除隔离")
        return

    verify = subprocess.run(
        ["codesign", "--verify", "--verbose=1", str(APP)],
        capture_output=True, text=True,
    )
    if verify.returncode == 0:
        log("  签名校验通过")
    else:
        # 不 deep 签名时，内嵌的 Chromium 自带签名可能不被视为已覆盖，属预期
        log(f"  [!] 校验提示：{verify.stderr.strip()[:200]}")


def make_dmg(arch: str) -> Path | None:
    log("\n=== [7/7] 生成 dmg ===")
    stage = DIST / "dmg_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    shutil.copytree(APP, stage / APP.name, symlinks=True)
    (stage / "Applications").symlink_to("/Applications")

    dmg = DIST / f"{APP_NAME}-{arch}.dmg"
    if dmg.exists():
        dmg.unlink()
    result = subprocess.run([
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", str(stage),
        "-ov", "-format", "UDZO",
        str(dmg),
    ], capture_output=True, text=True)
    shutil.rmtree(stage, ignore_errors=True)
    if result.returncode != 0:
        log(f"  [!] dmg 创建失败：{result.stderr.strip()}")
        return None
    log(f"  {dmg.name}  {dmg.stat().st_size / 1e6:.0f}MB")
    return dmg


def selftest() -> None:
    log("\n=== 自检 ===")
    exe = APP / "Contents" / "MacOS" / APP_NAME
    if not exe.exists():
        log(f"  [!] 未找到可执行文件：{exe}")
        return
    result = subprocess.run([str(exe), "--selftest"], capture_output=True, text=True, timeout=180)
    log_path = Path.home() / "Library" / "Application Support" / "MatrixPublisher" / "selftest.log"
    if log_path.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-25:]
        log("\n".join("  " + line for line in tail))
        if "FAIL" in log_path.read_text(encoding="utf-8", errors="replace"):
            log("  [!] 自检存在 FAIL 项")
    else:
        log(f"  [!] 自检日志未生成（退出码 {result.returncode}）")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 macOS 客户端")
    parser.add_argument("--skip-deps", action="store_true", help="跳过依赖检查与安装")
    parser.add_argument("--no-dmg", action="store_true", help="只生成 .app，不打包 dmg")
    parser.add_argument("--deep-sign", action="store_true",
                        help="对嵌套的 Chromium 一并重签（可能破坏其 JIT 权限，非必要不要开）")
    parser.add_argument("--identity", default=os.environ.get("MATRIX_SIGN_IDENTITY", ""),
                        help="Developer ID 签名证书名；留空则 ad-hoc 签名")
    parser.add_argument("--version", default=os.environ.get("MATRIX_VERSION", "1.0.0"))
    parser.add_argument("--force-icon", action="store_true", help="强制重新生成 icns")
    args = parser.parse_args()

    if sys.platform != "darwin":
        log("[x] 当前不是 macOS，PyInstaller 无法交叉编译。")
        log("    请在一台 Mac 上运行本脚本，或用 .github/workflows/build-macos.yml 走 CI。")
        return 2

    arch = platform.machine()  # arm64 / x86_64
    log(f"目标架构：{arch}    Python：{sys.version.split()[0]}    PyInstaller 构建目录：{DIST.name}")

    if not args.skip_deps:
        ensure_dependencies()
    else:
        log("[1/7] 跳过依赖安装")

    browser_root = ensure_chromium()
    make_icns(force=args.force_icon)
    build_app(args.version)
    bundle_browsers(browser_root)
    sign_app(args.identity, args.deep_sign)

    if not args.no_dmg:
        make_dmg(arch)

    selftest()

    log("\n构建完成：")
    log(f"  {APP}")
    log(f"  用户数据目录：~/Library/Application Support/MatrixPublisher")
    if not args.identity:
        log("\n提示：ad-hoc 签名只适合本机/内部使用。分发给别人时对方可能需要执行")
        log("      xattr -dr com.apple.quarantine /Applications/视频矩阵分发.app")
        log("      正式分发请用 Developer ID 证书签名并做公证（notarytool）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
