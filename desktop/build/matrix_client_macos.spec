# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：视频矩阵分发（macOS .app）。

必须在 macOS 上执行，PyInstaller 不支持交叉编译：
    python -m PyInstaller desktop/build/matrix_client_macos.spec --noconfirm

架构跟随当前解释器：在 arm64 的 Python 下打出来就是 Apple Silicon 版，
在 x86_64 的 Python（或 Rosetta 下的 Python）下打出来就是 Intel 版。
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
RESOURCES = PROJECT_ROOT / "desktop" / "resources"
ICON = RESOURCES / "app.icns"

APP_NAME = "视频矩阵分发"
BUNDLE_ID = "com.kebenxiaoming.matrixpublisher"
VERSION = os.environ.get("MATRIX_VERSION", "1.0.0")

hidden_imports = [
    # 平台上传器
    "douyin_uploader", "douyin_uploader.main",
    "tencent_uploader", "tencent_uploader.main",
    "ks_uploader", "ks_uploader.main",
    "xhs_uploader", "xhs_uploader.main",
    "utils", "utils.cache_store", "utils.files_times", "utils.constant",
    "utils.login_diag", "utils.browser_login", "utils.browser_mode",
    "conf",
    # 桌面端
    "desktop", "desktop.core", "desktop.core.paths", "desktop.core.config",
    "desktop.core.database", "desktop.core.login_service",
    "desktop.core.publish_service", "desktop.core.xhs_signer",
    "desktop.ui", "desktop.ui.theme", "desktop.ui.icon", "desktop.ui.main_window",
    "desktop.ui.widgets", "desktop.ui.widgets.common",
    "desktop.ui.pages", "desktop.ui.pages.dashboard", "desktop.ui.pages.accounts",
    "desktop.ui.pages.publish", "desktop.ui.pages.queue",
    "desktop.ui.pages.logs", "desktop.ui.pages.settings",
    # 第三方
    "playwright", "playwright.sync_api", "playwright.async_api",
    "playwright._impl._api_types", "playwright._impl._sync_base",
    "greenlet", "pyee",
    "xhs", "qrcode", "PIL", "PIL.Image", "requests", "sqlite3",
    "lxml", "lxml.etree",
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
]

datas = [
    # 小红书签名所需的 stealth 脚本，运行时会被复制到数据目录
    (str(RESOURCES / "xhs_uploader" / "*.js"), "xhs_uploader"),
]

excludes = [
    "tkinter", "matplotlib", "numpy", "pandas", "scipy",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtQuick", "PySide6.QtQuick3D",
    "PySide6.QtNetworkAuth", "PySide6.QtPdf", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtOpenGL", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSvgWidgets",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtXml",
    "flask", "jinja2", "werkzeug", "redis", "pymysql",
]

a = Analysis(
    [str(PROJECT_ROOT / "desktop" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=str(ICON) if ICON.exists() else None,
    bundle_identifier=BUNDLE_ID,
    version=VERSION,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": APP_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        # 用户要从这些目录挑视频，未声明会直接被 TCC 拦掉
        "NSDesktopFolderUsageDescription": "需要读取你选择的视频文件用于发布。",
        "NSDocumentsFolderUsageDescription": "需要读取你选择的视频文件用于发布。",
        "NSDownloadsFolderUsageDescription": "需要读取你选择的视频文件用于发布。",
        "NSMoviesFolderUsageDescription": "需要读取你选择的视频文件用于发布。",
    },
)
