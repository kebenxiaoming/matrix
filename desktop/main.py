# -*- coding: utf-8 -*-
"""桌面客户端入口。"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# 打包为无控制台程序后 stdout/stderr 为 None，直接 print 会抛异常
if sys.stdout is None or sys.stderr is None:
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null


def _setup_pythonpath() -> None:
    """保证打包后仍能导入项目根的 uploader 模块。"""
    for candidate in (APP_ROOT, Path(getattr(sys, "_MEIPASS", APP_ROOT))):
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def _setup_playwright_env() -> None:
    """让 Playwright 使用随包分发的浏览器目录。"""
    from desktop.core import paths

    if not paths.is_frozen():
        return
    candidates = [paths.app_root() / "ms-playwright"]
    if sys.platform == "darwin":
        # .app 里资源可能在 Contents/Resources 或 Contents/Frameworks
        candidates.append(paths.app_root().parent / "Resources" / "ms-playwright")
        candidates.append(paths.app_root().parent / "Frameworks" / "ms-playwright")
    candidates.append(paths.resource_root() / "ms-playwright")
    for bundled in candidates:
        if bundled.is_dir():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
            return


def _install_excepthook(log_file: Path) -> None:
    def handler(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handler


def run_selftest() -> int:
    """--selftest：自检关键依赖，结果写入 data/selftest.log（GUI 程序没有控制台）。"""
    from desktop.core import paths

    lines: list[str] = []

    def log(message: str) -> None:
        lines.append(message)

    log(f"frozen        = {paths.is_frozen()}")
    log(f"app_root      = {paths.app_root()}")
    log(f"resource_root = {paths.resource_root()}")
    log(f"data_root     = {paths.data_root()}")
    log(f"sys.path[0]   = {sys.path[0]}")
    log(f"PLAYWRIGHT_BROWSERS_PATH = {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")

    ok = True
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            exe = Path(playwright.chromium.executable_path)
            log(f"chromium exe  = {exe}  exists={exe.exists()}")
            if not exe.exists():
                ok = False
            else:
                browser = playwright.chromium.launch(headless=True, channel="chromium")
                page = browser.new_page()
                page.goto("about:blank")
                page.set_content("<h1>matrix selftest</h1>")
                title = page.locator("h1").inner_text()
                browser.close()
                log(f"headless launch ok, page text = {title}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        log(f"[x] playwright 自检失败: {type(exc).__name__}: {exc}")
        log(traceback.format_exc())

    for module in ("xhs", "lxml.etree", "qrcode", "PIL.Image", "requests", "sqlite3"):
        try:
            __import__(module)
            log(f"import {module} ok")
        except Exception as exc:  # noqa: BLE001
            ok = False
            log(f"[x] import {module} 失败: {exc}")

    try:
        import douyin_uploader.main  # noqa: F401
        import ks_uploader.main  # noqa: F401
        import tencent_uploader.main  # noqa: F401
        import xhs_uploader.main  # noqa: F401
        log("import 4 uploaders ok")
    except Exception as exc:  # noqa: BLE001
        ok = False
        log(f"[x] 上传器导入失败: {type(exc).__name__}: {exc}")
        log(traceback.format_exc())

    try:
        from desktop.core import database as db

        log(f"sqlite ok, accounts = {len(db.list_accounts())}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        log(f"[x] sqlite 失败: {exc}")

    try:
        from desktop.core import xhs_signer

        xhs_signer.install("local")
        log("xhs signer installed")
    except Exception as exc:  # noqa: BLE001
        ok = False
        log(f"[x] 签名器安装失败: {type(exc).__name__}: {exc}")

    log("RESULT = " + ("PASS" if ok else "FAIL"))
    target = paths.logs_dir() / "selftest.log"
    target.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


def _startup_logger():
    """启动过程打点，便于排查打包环境的偶发问题。"""
    from datetime import datetime

    from desktop.core import paths

    log_path = paths.logs_dir() / "startup.log"

    def log(message: str) -> None:
        try:
            if log_path.exists() and log_path.stat().st_size > 512 * 1024:
                log_path.unlink()
        except Exception:
            pass
        try:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")
        except Exception:
            pass

    return log


def main() -> int:
    _setup_pythonpath()

    from desktop.core import paths

    paths.prepare_runtime()
    _setup_playwright_env()

    log = _startup_logger()
    log("=== 启动 ===")
    log(f"frozen={paths.is_frozen()} app_root={paths.app_root()}")
    log(f"data_root={paths.data_root()}")

    if "--selftest" in sys.argv:
        return run_selftest()

    _install_excepthook(paths.logs_dir() / "runtime.log")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    from desktop.ui.icon import app_icon, ensure_ui_assets
    from desktop.ui.theme import build_style_sheet

    log("创建 QApplication")
    app = QApplication(sys.argv)
    app.setApplicationName("视频矩阵分发")
    app.setApplicationDisplayName("视频矩阵分发客户端")
    app.setOrganizationName("MatrixPublisher")
    app.setWindowIcon(app_icon())

    ui_assets = paths.data_root() / ".ui"
    ensure_ui_assets(ui_assets)
    app.setStyleSheet(build_style_sheet(ui_assets))
    log("QApplication 就绪")

    # 单实例：避免多个窗口同时消费同一个队列
    lock = None
    if os.environ.get("MATRIX_NO_SINGLE_INSTANCE") != "1":
        from PySide6.QtCore import QLockFile

        lock = QLockFile(str(paths.data_root() / ".instance.lock"))
        lock.setStaleLockTime(30_000)
        if not lock.tryLock(200):
            log("检测到已有实例在运行，退出")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(None, "已在运行", "视频矩阵分发客户端已经在运行中。")
            return 0
        log("单实例锁获取成功")
        app._matrix_single_instance_lock = lock  # 保持引用，防止被回收后释放锁

    try:
        from desktop.core import config

        from desktop.core import xhs_signer

        xhs_signer.install(config.get("xhs_signer", "local"))
        log("小红书签名器就绪")
    except Exception:
        log("小红书签名器安装失败：\n" + traceback.format_exc())

    log("构建主窗口")
    from desktop.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    log("主窗口已显示，进入事件循环")

    # 诊断用：--screenshot <路径>，由 Qt 自行渲染截图后退出
    if "--screenshot" in sys.argv:
        from PySide6.QtCore import QTimer

        index = sys.argv.index("--screenshot")
        target = sys.argv[index + 1] if len(sys.argv) > index + 1 else str(
            paths.logs_dir() / "screenshot.png"
        )
        page = None
        if "--page" in sys.argv:
            page_index = sys.argv.index("--page")
            if len(sys.argv) > page_index + 1:
                page = sys.argv[page_index + 1]

        def capture() -> None:
            if page:
                window._switch_page(page)
                app.processEvents()
            window.grab().save(target)
            log(f"截图已保存：{target}")
            app.quit()

        QTimer.singleShot(1500, capture)

    code = app.exec()
    log(f"事件循环结束，退出码 {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
