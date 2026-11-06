# -*- coding: utf-8 -*-
"""路径解析。同时兼容开发态运行与 PyInstaller 打包后的运行环境。"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "视频矩阵分发"
APP_DIR_NAME = "MatrixPublisher"

# 各平台的 cookie 目录名，与上传器代码中的约定保持一致
PLATFORM_DIRS = {
    1: "douyin_uploader",
    2: "tencent_uploader",
    3: "xhs_uploader",
    4: "ks_uploader",
}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """exe 所在目录（打包后）或项目根目录（开发时）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """随包分发的只读资源目录。

    macOS 的 .app 结构里 datas 落在 Contents/Resources，而 sys._MEIPASS 指向
    Contents/Frameworks，两者不一致，所以按"哪个目录里真有 xhs_uploader"来判定。
    """
    if is_frozen():
        mei = Path(getattr(sys, "_MEIPASS", app_root()))
        candidates: list[Path] = []
        if sys.platform == "darwin":
            candidates.append(app_root().parent / "Resources")
        candidates.append(mei)
        if sys.platform == "darwin":
            candidates.append(app_root().parent / "Frameworks")
        candidates.append(app_root())
        for candidate in candidates:
            if (candidate / "xhs_uploader").exists():
                return candidate
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return mei
    return app_root() / "desktop" / "resources"


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


_DATA_ROOT: Path | None = None


def _system_data_dir() -> Path:
    """各系统的标准用户数据目录。"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home())) / APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


def data_root() -> Path:
    """可写的用户数据目录。

    Windows/Linux：优先使用 exe 同级的 data 目录（绿色便携，拷走即可迁移），
    若该位置不可写（例如装在 Program Files）则退回到系统数据目录。

    macOS：打包后 .app 是 bundle，往 Contents/MacOS/data 写会让签名失效，
    且升级替换 .app 时数据会丢，所以固定用 ~/Library/Application Support。
    """
    global _DATA_ROOT
    if _DATA_ROOT is not None:
        return _DATA_ROOT

    override = os.environ.get("MATRIX_DATA_DIR")
    if override:
        candidate = Path(override)
        candidate.mkdir(parents=True, exist_ok=True)
        _DATA_ROOT = candidate
        return _DATA_ROOT

    if sys.platform == "darwin" and is_frozen():
        roaming = _system_data_dir()
        roaming.mkdir(parents=True, exist_ok=True)
        _DATA_ROOT = roaming
        return _DATA_ROOT

    portable = app_root() / "data"
    if _is_writable(portable):
        _DATA_ROOT = portable
        return _DATA_ROOT

    roaming = _system_data_dir()
    roaming.mkdir(parents=True, exist_ok=True)
    _DATA_ROOT = roaming
    return _DATA_ROOT


def logs_dir() -> Path:
    path = data_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def accounts_dir() -> Path:
    path = data_root() / "accounts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def platform_account_dir(platform: int) -> Path:
    """某个平台的 cookie 存放目录（上传器会在此目录下生成 json 文件）。"""
    path = accounts_dir() / PLATFORM_DIRS.get(platform, f"platform_{platform}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_root() / "matrix.db"


def config_path() -> Path:
    return data_root() / "config.json"


def _copy_tree_if_missing(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_tree_if_missing(item, target)
        elif not target.exists():
            try:
                shutil.copy2(item, target)
            except Exception:
                pass


def prepare_runtime() -> Path:
    """初始化运行目录，并把 BASE_DIR 重定向到可写的数据目录。

    上传器代码用 conf.BASE_DIR 定位 stealth 脚本、缓存等资源；
    打包后代码目录可能不可写，因此统一指向 data_root()。
    返回数据目录。
    """
    root = data_root()
    os.environ["MATRIX_BASE_DIR"] = str(root)
    os.environ.setdefault("MATRIX_CACHE_BACKEND", "local")

    # 静态资源：小红书签名依赖的 stealth.min.js
    res = resource_root()
    for rel in ("xhs_uploader", "xhs-api"):
        src = res / rel
        if src.exists():
            _copy_tree_if_missing(src, root / rel)

    for platform in PLATFORM_DIRS:
        platform_account_dir(platform)

    logs_dir()
    return root
