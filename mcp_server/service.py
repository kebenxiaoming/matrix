# -*- coding: utf-8 -*-
"""MCP 工具的业务实现。

原则：
1. 所有对外返回都是 dict，不抛异常——AI 需要读到结构化的 code 才能自己纠正。
2. 发布全局串行。四个平台都要开 Chrome、共用账号 cookie，并发只会互相踩。
3. 不返回 cookie 内容，只返回"有没有登录"。
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from . import settings

PLATFORM_KEYS = {"douyin": 1, "tencent": 2, "xhs": 3, "ks": 4}
PLATFORM_ALIASES = {
    "抖音": "douyin",
    "视频号": "tencent",
    "微信视频号": "tencent",
    "小红书": "xhs",
    "快手": "ks",
}

_QUEUE: "queue.Queue[int | None]" = queue.Queue()
_WORKER_LOCK = threading.Lock()
_WORKER_STARTED = False
_EXEC_LOCK = threading.Lock()
_LOG_LOCK = threading.Lock()


# --------------------------------------------------------------------------- 基础

def _db():
    from desktop.core import database

    return database


def _log_file(message: str) -> None:
    try:
        path = settings.data_dir() / "logs" / "mcp.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            if path.exists() and path.stat().st_size > 2 * 1024 * 1024:
                path.unlink()
            with open(path, "a", encoding="utf-8") as handle:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def _ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, **fields}


def _err(code: str, message: str, **fields: Any) -> dict[str, Any]:
    return {"ok": False, "code": code, "error": message, **fields}


def resolve_platform(value: Any) -> str | None:
    """把 douyin / 抖音 / 1 统一成 key。"""
    if value is None:
        return None
    raw = str(value).strip()
    low = raw.lower()
    if low in PLATFORM_KEYS:
        return low
    if raw in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[raw]
    if raw.isdigit() and int(raw) in (1, 2, 3, 4):
        for key, pid in PLATFORM_KEYS.items():
            if pid == int(raw):
                return key
    return None


def list_platforms() -> dict[str, Any]:
    db = _db()
    return _ok(platforms=[
        {
            "key": key,
            "id": pid,
            "name": db.PLATFORMS[pid],
            "aliases": [k for k, v in PLATFORM_ALIASES.items() if v == key],
        }
        for key, pid in PLATFORM_KEYS.items()
    ])


# --------------------------------------------------------------------------- 账号

def _account_public(row: dict[str, Any]) -> dict[str, Any]:
    db = _db()
    cookie = row.get("cookie_file") or ""
    return {
        "account_id": int(row["id"]),
        "platform": next((k for k, v in PLATFORM_KEYS.items() if v == row["platform"]), ""),
        "platform_name": db.PLATFORMS.get(row["platform"], ""),
        "username": row.get("username") or "",
        "third_id": row.get("third_id") or "",
        "status": db.ACCOUNT_STATUS.get(row.get("status", 0), "未知"),
        "cookie_present": bool(cookie) and Path(cookie).exists(),
        "last_login_at": row.get("last_login_at") or 0,
    }


def list_accounts(platform: str | None = None) -> dict[str, Any]:
    db = _db()
    key = resolve_platform(platform) if platform else None
    if platform and key is None:
        return _err("UNSUPPORTED_PLATFORM", f"未知平台：{platform}", allowed=list(PLATFORM_KEYS))
    rows = db.list_accounts(PLATFORM_KEYS[key] if key else None)
    return _ok(count=len(rows), accounts=[_account_public(r) for r in rows])


def check_login(account_id: int) -> dict[str, Any]:
    from desktop.core.auth import check_cookie

    db = _db()
    account = db.get_account(int(account_id))
    if not account:
        return _err("ACCOUNT_NOT_FOUND", f"账号 {account_id} 不存在")
    if not (account.get("cookie_file") or "") or not Path(account["cookie_file"]).exists():
        return _err("NEED_HUMAN_LOGIN",
                    "该账号没有登录信息，需要调 matrix_login 扫码",
                    account_id=int(account_id))
    started = time.time()
    valid = check_cookie(int(account["platform"]), account)
    if not valid:
        db.mark_account_status(int(account_id), 2)
        return _err("NEED_HUMAN_LOGIN",
                    "登录已失效，需要调 matrix_login 重新扫码",
                    account_id=int(account_id),
                    elapsed=round(time.time() - started, 1))
    return _ok(account_id=int(account_id), valid=True,
               elapsed=round(time.time() - started, 1))


# --------------------------------------------------------------------------- 登录

def _open_path(path: str) -> None:
    """用系统默认程序打开文件（小红书二维码是 PNG，得让用户看到）。"""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def login(
    platform: str | None = None,
    account_id: int | None = None,
    show_qrcode: bool = True,
) -> dict[str, Any]:
    """扫码登录，返回登录后的账号信息。

    抖音/视频号/快手会弹出有头浏览器，二维码在窗口里；小红书没有窗口，
    二维码是本地 PNG，用系统看图器打开。
    """
    from desktop.core import login_flow

    db = _db()
    key = resolve_platform(platform) if platform else None
    if platform and key is None:
        return _err("UNSUPPORTED_PLATFORM", f"未知平台：{platform}",
                    allowed=list(PLATFORM_KEYS))

    created: int | None = None
    if account_id is not None:
        account = db.get_account(int(account_id))
        if not account:
            return _err("ACCOUNT_NOT_FOUND", f"账号 {account_id} 不存在")
        if key and int(account["platform"]) != PLATFORM_KEYS[key]:
            return _err("PLATFORM_MISMATCH",
                        f"账号 {account_id} 属于{db.PLATFORMS.get(account['platform'], '')}，"
                        f"与请求的平台 {key} 不一致")
        pid = int(account["platform"])
        target_id = int(account["id"])
    else:
        if key is None:
            return _err("BAD_ARGUMENT", "platform 和 account_id 至少提供一个")
        pid = PLATFORM_KEYS[key]
        target_id = int(db.create_account(pid))
        created = target_id
        _log_file(f"登录前创建占位账号 {target_id}（{key}）")

    qr: dict[str, Any] = {}

    def _log(message: str, level: str = "INFO") -> None:
        _log_file(f"[login {target_id}] [{level}] {message}")

    def _on_qrcode(path: str) -> None:
        qr["path"] = str(path)
        _log(f"二维码已生成：{path}")
        if show_qrcode:
            _open_path(str(path))

    # 登录和发布都开 Chrome、都写 cookie，必须互斥。别让它无限等队列。
    if not _EXEC_LOCK.acquire(timeout=30):
        if created:
            db.delete_account(created)
        return _err("BUSY", "发布队列正在执行任务，稍后再试")
    started = time.time()
    try:
        info = login_flow.perform_login(pid, target_id, log=_log, on_qrcode=_on_qrcode)
    except login_flow.LoginError as exc:
        if created:
            db.delete_account(created)
        return _err("LOGIN_FAILED", str(exc),
                    platform=key or str(pid),
                    hint="二维码约 5 分钟内有效；窗口被关掉或超时都会失败，重试即可",
                    elapsed=round(time.time() - started, 1))
    except Exception as exc:  # noqa: BLE001
        _log_file(f"登录异常：\n{traceback.format_exc()}")
        if created:
            db.delete_account(created)
        return _err("LOGIN_FAILED", f"{type(exc).__name__}: {exc}",
                    platform=key or str(pid))
    finally:
        _EXEC_LOCK.release()

    if not info:
        if created:
            db.delete_account(created)
        return _err("LOGIN_FAILED", "扫码登录未完成或已超时", platform=key or str(pid))

    # 同一第三方账号已存在时，save_account_login 会合并到旧记录并删掉占位行，
    # 所以这里按 third_id 重新查一遍，返回真正存活的那个 id。
    third_id = str(info.get("account_id") or "")
    survived = None
    for row in db.list_accounts(pid):
        if str(row.get("third_id") or "") == third_id:
            survived = row
            break
    final = survived or db.get_account(target_id) or {}

    return _ok(
        account_id=int(final.get("id") or target_id),
        platform=key or str(pid),
        platform_name=db.PLATFORMS.get(pid, ""),
        username=str(info.get("username") or ""),
        third_id=third_id,
        elapsed=round(time.time() - started, 1),
        **({"qrcode_path": qr["path"]} if qr.get("path") else {}),
        note="已登录并保存凭据；现在可以发布",
    )


# --------------------------------------------------------------------------- 媒体校验

def _is_inside(path: Path, root: Path) -> bool:
    try:
        return path == root or root in path.parents
    except Exception:
        return False


def _resolve_media(raw: str, exts: set[str], label: str) -> Path:
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    try:
        path = path.resolve()
    except Exception:
        return None  # type: ignore[return-value]

    if not path.exists() or not path.is_file():
        raise ValueError(f"{label}不存在：{path}")
    if path.suffix.lower() not in exts:
        raise ValueError(f"{label}格式不支持（{path.suffix}），支持：{', '.join(sorted(exts))}")

    roots = settings.allowed_roots()
    if roots and not any(_is_inside(path, root) for root in roots):
        allowed = "、".join(str(r) for r in roots)
        raise PermissionError(
            f"{label}不在允许目录内。当前允许：{allowed}。"
            f"如需放开，设置环境变量 MATRIX_ALLOWED_DIRS（多个目录用 {os.pathsep} 分隔）"
        )
    return path


def _normalize_publish_at(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(text, fmt))
        except ValueError:
            continue
    raise ValueError("publish_at 格式应为 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD HH:MM:SS'")


# --------------------------------------------------------------------------- 队列

def _ensure_worker() -> None:
    global _WORKER_STARTED
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        thread = threading.Thread(target=_worker_loop, name="matrix-publisher", daemon=True)
        thread.start()
        _WORKER_STARTED = True
    _log_file("发布队列已启动")


def _worker_loop() -> None:
    while True:
        task_id = _QUEUE.get()
        if task_id is None:
            continue
        try:
            _execute(task_id)
        except Exception:  # noqa: BLE001
            _log_file("队列执行异常：\n" + traceback.format_exc())
        finally:
            _QUEUE.task_done()
        if settings.TASK_GAP > 0:
            time.sleep(settings.TASK_GAP)


def _make_logger(task_id: int, source: str):
    db = _db()

    def _log(message: str, level: str = "INFO") -> None:
        try:
            db.add_log(message, level, source, task_id)
        except Exception:
            pass
        _log_file(f"[{level}] [task {task_id}] {message}")

    return _log


def _execute(task_id: int) -> None:
    from desktop.core.publisher import publish_one

    db = _db()
    task = db.get_task(task_id)
    if not task:
        _log_file(f"任务 {task_id} 不存在，跳过")
        return
    if task["status"] not in (0, 1):
        _log_file(f"任务 {task_id} 状态为 {task['status']}，跳过")
        return

    source = db.PLATFORMS.get(task["platform"], "")
    db.update_task(task_id, status=1)
    logger = _make_logger(task_id, source)
    logger("任务开始")

    with _EXEC_LOCK:
        try:
            status, error = publish_one(task, logger)
        except Exception as exc:  # noqa: BLE001
            _log_file(f"任务 {task_id} 异常：\n" + traceback.format_exc())
            status, error = 3, f"{type(exc).__name__}: {exc}"

    db.update_task(
        task_id, status=status, error=error,
        finished_at=int(time.time()) if status in (2, 3, 4) else 0,
    )
    logger(f"任务结束：{db.TASK_STATUS.get(status, status)} {error}".strip())


def _enqueue(task_id: int) -> None:
    _ensure_worker()
    _QUEUE.put(int(task_id))


def _wait(task_id: int, timeout: int) -> dict[str, Any]:
    db = _db()
    deadline = time.time() + max(5, timeout)
    while time.time() < deadline:
        task = db.get_task(task_id)
        if task and task["status"] in (2, 3, 4, 5):
            return _task_result(task)
        time.sleep(0.5)
    return _err(
        "TIMEOUT",
        f"任务 {task_id} 在 {timeout}s 内没有结束，仍在后台队列中；可用 matrix_task_status 查询",
        task_id=int(task_id),
        status="pending",
    )


def _task_result(task: dict[str, Any]) -> dict[str, Any]:
    db = _db()
    status = int(task["status"])
    elapsed = 0
    if task.get("finished_at") and task.get("created_at"):
        elapsed = int(task["finished_at"]) - int(task["created_at"])
    result = {
        "task_id": int(task["id"]),
        "status_code": status,
        "status": db.TASK_STATUS.get(status, "未知"),
        "elapsed_seconds": elapsed,
    }
    if status == 2:
        result["ok"] = True
        return result
    return _err("PUBLISH_FAILED" if status == 3 else "NEED_HUMAN_LOGIN",
                task.get("error") or "发布未成功", **result)


# --------------------------------------------------------------------------- 发布

def publish(
    platform: str,
    account_id: int,
    video_path: str,
    title: str = "",
    tags: list[str] | None = None,
    cover_path: str | None = None,
    description: str = "",
    location: str | None = None,
    publish_at: str | None = None,
    dry_run: bool = False,
    timeout: int | None = None,
) -> dict[str, Any]:
    from desktop.core import config
    from desktop.core.auth import check_cookie

    db = _db()
    key = resolve_platform(platform)
    if key is None:
        return _err("UNSUPPORTED_PLATFORM", f"未知平台：{platform}",
                    allowed=list(PLATFORM_KEYS))

    account = db.get_account(int(account_id))
    if not account:
        return _err("ACCOUNT_NOT_FOUND", f"账号 {account_id} 不存在")
    if int(account["platform"]) != PLATFORM_KEYS[key]:
        return _err(
            "PLATFORM_MISMATCH",
            f"账号 {account_id} 属于{db.PLATFORMS.get(account['platform'], '')}，"
            f"与请求的平台 {key} 不一致",
        )

    cookie_file = account.get("cookie_file") or ""
    if not cookie_file or not Path(cookie_file).exists():
        return _err("NEED_HUMAN_LOGIN",
                    "该账号没有登录信息，请先调 matrix_login 扫码登录",
                    account_id=int(account_id))

    try:
        video = _resolve_media(video_path, settings.VIDEO_EXTS, "视频")
        cover = _resolve_media(cover_path, settings.IMAGE_EXTS, "封面") if cover_path else None
        scheduled = _normalize_publish_at(publish_at)
    except (ValueError, PermissionError) as exc:
        code = "PATH_NOT_ALLOWED" if isinstance(exc, PermissionError) else "BAD_ARGUMENT"
        return _err(code, str(exc))

    tag_text = ",".join(str(t).strip().lstrip("#") for t in (tags or []) if str(t).strip())
    final_title = (title or video.stem).strip()[:50]

    if dry_run:
        valid = check_cookie(int(account["platform"]), account)
        return {
            "ok": bool(valid),
            "dry_run": True,
            "code": "" if valid else "NEED_HUMAN_LOGIN",
            "error": "" if valid else "登录已失效，需要重新扫码",
            "platform": key,
            "account_id": int(account_id),
            "video_path": str(video),
            "cover_path": str(cover) if cover else "",
            "title": final_title,
            "tags": tag_text,
            "publish_at": scheduled,
        }

    payload = {
        "title": final_title,
        "description": description or "",
        "tags": tag_text,
        "video_path": str(video),
        "cover_path": str(cover) if cover else "",
        "location": location or config.get("default_location") or "",
        "publish_at": scheduled,
    }
    _, task_ids = db.create_tasks_detailed([int(account_id)], payload)
    if not task_ids:
        return _err("CREATE_FAILED", "任务创建失败")

    task_id = task_ids[0]
    _log_file(f"创建任务 {task_id}：{key} / {final_title}")
    _enqueue(task_id)
    return _wait(task_id, timeout or settings.PUBLISH_TIMEOUT)


def publish_batch(
    items: list[dict[str, Any]],
    timeout: int = 0,
) -> dict[str, Any]:
    """批量入队后立即返回，不等待执行。"""
    from desktop.core import config

    db = _db()
    if not items:
        return _err("BAD_ARGUMENT", "items 不能为空")

    created: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        platform = item.get("platform")
        key = resolve_platform(platform)
        account_id = item.get("account_id")
        if key is None or account_id is None:
            rejected.append({"index": index, "reason": "platform 或 account_id 缺失"})
            continue
        account = db.get_account(int(account_id))
        if not account:
            rejected.append({"index": index, "account_id": account_id, "reason": "账号不存在"})
            continue
        if int(account["platform"]) != PLATFORM_KEYS[key]:
            rejected.append({"index": index, "account_id": account_id, "reason": "平台与账号不匹配"})
            continue
        cookie_file = account.get("cookie_file") or ""
        if not cookie_file or not Path(cookie_file).exists():
            rejected.append({"index": index, "account_id": account_id,
                             "reason": "该账号未登录，需要先扫码"})
            continue
        try:
            video = _resolve_media(item.get("video_path", ""), settings.VIDEO_EXTS, "视频")
            cover = _resolve_media(item["cover_path"], settings.IMAGE_EXTS, "封面") \
                if item.get("cover_path") else None
            scheduled = _normalize_publish_at(item.get("publish_at"))
        except (ValueError, PermissionError) as exc:
            rejected.append({"index": index, "account_id": account_id, "reason": str(exc)})
            continue

        tags = item.get("tags") or []
        payload = {
            "title": (item.get("title") or video.stem).strip()[:50],
            "description": item.get("description") or "",
            "tags": ",".join(str(t).strip().lstrip("#") for t in tags if str(t).strip()),
            "video_path": str(video),
            "cover_path": str(cover) if cover else "",
            "location": item.get("location") or config.get("default_location") or "",
            "publish_at": scheduled,
        }
        batch_id, task_ids = db.create_tasks_detailed([int(account_id)], payload)
        if task_ids:
            created.append({"index": index, "task_id": task_ids[0], "batch_id": batch_id})

    for entry in created:
        _enqueue(entry["task_id"])

    if not created:
        return _err("CREATE_FAILED", "没有任何任务创建成功", rejected=rejected)

    return _ok(
        queued=len(created),
        rejected=rejected,
        tasks=created,
        note="任务已在后台串行执行；用 matrix_task_status 查询进度",
    )


# --------------------------------------------------------------------------- 状态

def task_status(task_id: int | None = None, batch_id: str | None = None) -> dict[str, Any]:
    db = _db()
    if task_id is None and not batch_id:
        return _err("BAD_ARGUMENT", "task_id 和 batch_id 至少提供一个")

    if task_id is not None:
        task = db.get_task(int(task_id))
        if not task:
            return _err("TASK_NOT_FOUND", f"任务 {task_id} 不存在")
        result = _task_result(task)
        result["task"] = _task_summary(task)
        return result

    rows = db.list_batch_tasks(str(batch_id))
    if not rows:
        return _err("TASK_NOT_FOUND", f"批次 {batch_id} 没有任务")
    done = sum(1 for r in rows if r["status"] in (2, 3, 4, 5))
    return _ok(
        batch_id=batch_id,
        total=len(rows),
        done=done,
        pending=len(rows) - done,
        tasks=[_task_summary(r) for r in rows],
    )


def _task_summary(row: dict[str, Any]) -> dict[str, Any]:
    db = _db()
    return {
        "task_id": int(row["id"]),
        "platform_name": db.PLATFORMS.get(row["platform"], ""),
        "account_id": int(row["account_id"]),
        "title": row.get("title") or "",
        "status": db.TASK_STATUS.get(int(row["status"]), "未知"),
        "status_code": int(row["status"]),
        "publish_at": row.get("publish_at") or "",
        "error": row.get("error") or "",
    }


def health() -> dict[str, Any]:
    from utils.browser_mode import find_chrome_executable, headless_enabled

    db = _db()
    info: dict[str, Any] = {
        "ok": True,
        "data_dir": str(settings.data_dir()),
        "headless": headless_enabled(),
        "allowed_dirs": [str(p) for p in settings.allowed_roots()],
        "accounts": len(db.list_accounts()),
        "pending_tasks": len(db.list_tasks(status=0, limit=1000)),
        "queue_alive": _WORKER_STARTED,
        "platforms": list(PLATFORM_KEYS),
    }
    chrome = find_chrome_executable()
    info["chrome"] = chrome or ""
    info["chrome_ok"] = bool(chrome)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            info["chromium"] = playwright.chromium.executable_path
    except Exception as exc:  # noqa: BLE001
        info["chromium"] = ""
        info["playwright_error"] = str(exc)

    if not chrome:
        info["warnings"] = [
            "未找到系统 Chrome：视频号和小红书依赖 h264 编码，内置 Chromium 可能传不动，"
            "建议先安装 Google Chrome",
        ]
    return info
