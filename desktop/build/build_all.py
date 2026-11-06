# -*- coding: utf-8 -*-
"""一键构建：生成图标 → PyInstaller 打包 → 复制浏览器资源。

用法（在项目根目录执行）：
    .venv-desktop\\Scripts\\python.exe desktop\\build\\build_all.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "desktop" / "build"


def run(cmd: list[str], title: str) -> None:
    print(f"\n=== {title} ===")
    print("  " + " ".join(cmd))
    started = time.time()
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"[x] 失败（退出码 {result.returncode}）")
        sys.exit(result.returncode)
    print(f"  完成，用时 {time.time() - started:.1f}s")


def archive_previous_app(rename_only: bool = True) -> Path | None:
    """把上一次的成品**子目录**改名归档。

    注意只改 ``dist/视频矩阵分发``，不动 ``dist`` 本身：只要有进程把 dist 当作
    工作目录（比如客户端从 dist 下启动过），Windows 就会拒绝重命名 dist，
    换个子目录名则不受影响。
    """
    dist = ROOT / "dist"
    app = dist / "视频矩阵分发"
    if not app.exists():
        return None
    stamp = time.strftime("%H%M%S")
    target = ROOT / f"dist_old_{stamp}"
    app.rename(target)
    print(f"  已归档旧构建 -> {target.name}")
    return target


def publish_app(build_output: Path) -> None:
    """把新构建的子目录搬进 dist（源在 dist_new，避免污染已有 dist）。"""
    import shutil

    fresh = build_output / "视频矩阵分发"
    if not fresh.exists():
        raise SystemExit(f"[x] 未找到新构建输出：{fresh}")
    target = ROOT / "dist" / "视频矩阵分发"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    fresh.rename(target)
    print(f"  新构建已就位 -> {target}")
    # dist_new 里若已空就顺手删掉
    try:
        if not any(build_output.iterdir()):
            build_output.rmdir()
    except Exception:
        pass


def preserve_data() -> Path | None:
    """把成品目录里的 data（账号、cookie、数据库、日志）先备份出来。

    重新打包会重建 dist，用户已经登录的账号和排好的任务都在 data 下，
    不备份等于每次升级都要重新扫码。
    """
    import shutil

    store = ROOT / "build_tmp" / "preserved_data"
    data = ROOT / "dist" / "视频矩阵分发" / "data"
    if not data.exists():
        # 上一次构建被中断时 dist 可能已经不存在，此时沿用已备份的数据，不能丢
        if store.exists() and any(store.iterdir()):
            print(f"  沿用上次备份的用户数据 -> {store.name}")
            return store
        return None
    if store.exists():
        shutil.rmtree(store, ignore_errors=True)
    store.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        data, store, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".instance.lock", ".cache"),
    )
    print(f"  已备份用户数据 -> {store.name}")
    return store


def restore_data(store: Path | None) -> None:
    """构建完成后把备份的用户数据合并回新成品目录。"""
    import shutil

    if store is None or not store.exists():
        return
    target = ROOT / "dist" / "视频矩阵分发" / "data"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(store, target, dirs_exist_ok=True)
    print(f"  已恢复用户数据 -> {target}")


def main() -> int:
    python = sys.executable
    build_output = ROOT / "dist_new"

    store = preserve_data()
    archive_previous_app()

    run([python, str(BUILD / "make_icon.py")], "生成应用图标")

    run([
        python, "-m", "PyInstaller", str(BUILD / "matrix_client.spec"),
        "--noconfirm", "--distpath", str(build_output),
        "--workpath", str(ROOT / "build_tmp"),
    ], "PyInstaller 打包")

    publish_app(build_output)

    run([python, str(BUILD / "post_build.py")], "复制 Playwright 浏览器")

    restore_data(store)

    print("\n构建完成。成品目录：", ROOT / "dist" / "视频矩阵分发")
    print("提示：dist_old_* 是历史构建，确认新版可用后可手动删除。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
