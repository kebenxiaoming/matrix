# -*- coding: utf-8 -*-
"""SQLite 数据层：替代原项目的 MySQL + Redis 队列。

表结构与原 matrix.sql 的语义保持一致，但简化为单机客户端所需的三张表：
  accounts  账号（原 mx_account_info）
  tasks     发布任务（原 mx_publish_task_video_queue）
  logs      操作日志（新增，便于界面展示）
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths

PLATFORMS = {1: "抖音", 2: "视频号", 3: "小红书", 4: "快手"}
PLATFORM_KEYS = {"douyin": 1, "tencent": 2, "xhs": 3, "ks": 4}

TASK_STATUS = {
    0: "等待中",
    1: "发布中",
    2: "已成功",
    3: "失败",
    4: "登录失效",
    5: "已取消",
}

ACCOUNT_STATUS = {0: "未登录", 1: "正常", 2: "已失效"}

_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    platform      INTEGER NOT NULL,
    third_id      TEXT    NOT NULL DEFAULT '',
    username      TEXT    NOT NULL DEFAULT '',
    avatar        TEXT    NOT NULL DEFAULT '',
    cookie_file   TEXT    NOT NULL DEFAULT '',
    status        INTEGER NOT NULL DEFAULT 0,
    last_login_at INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL DEFAULT 0,
    updated_at    INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_platform_third
    ON accounts(platform, third_id) WHERE third_id <> '';

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id    TEXT    NOT NULL DEFAULT '',
    account_id  INTEGER NOT NULL,
    platform    INTEGER NOT NULL,
    title       TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '',
    video_path  TEXT    NOT NULL DEFAULT '',
    cover_path  TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL DEFAULT '',
    publish_at  TEXT    NOT NULL DEFAULT '',
    status      INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT    NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL DEFAULT 0,
    updated_at  INTEGER NOT NULL DEFAULT 0,
    finished_at INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, publish_at);

CREATE TABLE IF NOT EXISTS logs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      INTEGER NOT NULL DEFAULT 0,
    level   TEXT    NOT NULL DEFAULT 'INFO',
    source  TEXT    NOT NULL DEFAULT '',
    task_id INTEGER NOT NULL DEFAULT 0,
    message TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);
"""


def conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is not None:
        return _CONN
    path = paths.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _CONN = sqlite3.connect(str(path), check_same_thread=False, timeout=15)
    _CONN.row_factory = sqlite3.Row
    _CONN.execute("PRAGMA journal_mode=WAL")
    _CONN.execute("PRAGMA foreign_keys=ON")
    _CONN.executescript(SCHEMA)
    _CONN.commit()
    return _CONN


def close() -> None:
    global _CONN
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:
                pass
            _CONN = None


def _now() -> int:
    return int(time.time())


def _rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with _LOCK:
        cursor = conn().execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _row(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = _rows(sql, params)
    return rows[0] if rows else None


def _exec(sql: str, params: tuple = ()) -> int:
    with _LOCK:
        cursor = conn().execute(sql, params)
        conn().commit()
        return cursor.lastrowid or cursor.rowcount


# --------------------------------------------------------------------------- 账号

def list_accounts(platform: int | None = None) -> list[dict[str, Any]]:
    if platform:
        return _rows("SELECT * FROM accounts WHERE platform=? ORDER BY id DESC", (platform,))
    return _rows("SELECT * FROM accounts ORDER BY platform, id DESC")


def get_account(account_id: int) -> dict[str, Any] | None:
    return _row("SELECT * FROM accounts WHERE id=?", (account_id,))


def create_account(platform: int) -> int:
    ts = _now()
    return _exec(
        "INSERT INTO accounts (platform, status, created_at, updated_at) VALUES (?,?,?,?)",
        (platform, 0, ts, ts),
    )


def save_account_login(account_id: int, third_id: str, username: str, avatar: str,
                       cookie_file: str) -> None:
    """登录成功后落库；同一平台同一第三方账号就地更新，避免重复。"""
    ts = _now()
    with _LOCK:
        existing = conn().execute(
            "SELECT id FROM accounts WHERE platform=(SELECT platform FROM accounts WHERE id=?) "
            "AND third_id=? AND id<>?",
            (account_id, third_id, account_id),
        ).fetchone()
        if existing:
            # 已存在同平台同账号，合并到原记录上，删除占位行
            conn().execute(
                "UPDATE accounts SET status=1, username=?, avatar=?, cookie_file=?, "
                "last_login_at=?, updated_at=? WHERE id=?",
                (username, avatar, cookie_file, ts, ts, existing["id"]),
            )
            conn().execute("UPDATE tasks SET account_id=? WHERE account_id=?",
                           (existing["id"], account_id))
            conn().execute("DELETE FROM accounts WHERE id=?", (account_id,))
            conn().commit()
            return
        conn().execute(
            "UPDATE accounts SET third_id=?, username=?, avatar=?, cookie_file=?, status=1, "
            "last_login_at=?, updated_at=? WHERE id=?",
            (third_id, username, avatar, cookie_file, ts, ts, account_id),
        )
        conn().commit()


def mark_account_status(account_id: int, status: int) -> None:
    _exec("UPDATE accounts SET status=?, updated_at=? WHERE id=?", (status, _now(), account_id))


def delete_account(account_id: int) -> None:
    account = get_account(account_id)
    if account and account.get("cookie_file"):
        try:
            Path(account["cookie_file"]).unlink(missing_ok=True)
        except Exception:
            pass
    _exec("DELETE FROM accounts WHERE id=?", (account_id,))
    _exec("DELETE FROM tasks WHERE account_id=? AND status IN (0,1,5)", (account_id,))


# --------------------------------------------------------------------------- 任务

def create_tasks_detailed(account_ids: list[int],
                          payload: dict[str, Any]) -> tuple[str, list[int]]:
    """创建任务并返回 (batch_id, 新建的 task id 列表)。

    MCP 需要拿到 task_id 才能回查状态，原 create_tasks 只返回条数。
    """
    ts = _now()
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    created: list[int] = []
    with _LOCK:
        for account_id in account_ids:
            account = get_account(account_id)
            if not account:
                continue
            cursor = conn().execute(
                "INSERT INTO tasks (batch_id, account_id, platform, title, description, tags,"
                " video_path, cover_path, location, publish_at, status, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?)",
                (
                    batch_id, account_id, account["platform"],
                    payload.get("title", ""), payload.get("description", ""),
                    payload.get("tags", ""), payload.get("video_path", ""),
                    payload.get("cover_path", ""), payload.get("location", ""),
                    payload.get("publish_at", ""), ts, ts,
                ),
            )
            if cursor.lastrowid:
                created.append(int(cursor.lastrowid))
        conn().commit()
    return batch_id, created


def create_tasks(account_ids: list[int], payload: dict[str, Any]) -> int:
    _, created = create_tasks_detailed(account_ids, payload)
    return len(created)


def list_batch_tasks(batch_id: str) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM tasks WHERE batch_id=? ORDER BY id ASC", (batch_id,))


def list_tasks(status: int | None = None, limit: int = 500) -> list[dict[str, Any]]:
    sql = (
        "SELECT t.*, a.username AS account_name, a.avatar AS account_avatar "
        "FROM tasks t LEFT JOIN accounts a ON a.id = t.account_id "
    )
    if status is not None:
        sql += "WHERE t.status=? ORDER BY t.id DESC LIMIT ?"
        return _rows(sql, (status, limit))
    sql += "ORDER BY t.id DESC LIMIT ?"
    return _rows(sql, (limit,))


def get_task(task_id: int) -> dict[str, Any] | None:
    return _row("SELECT * FROM tasks WHERE id=?", (task_id,))


def update_task(task_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    keys = ", ".join(f"{k}=?" for k in fields)
    _exec(f"UPDATE tasks SET {keys} WHERE id=?", (*fields.values(), task_id))


def claim_next_task() -> dict[str, Any] | None:
    """取出下一个可执行任务：状态为等待中，且到达定时时间（或未设定时）。"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _LOCK:
        row = conn().execute(
            "SELECT * FROM tasks WHERE status=0 "
            "AND (publish_at='' OR publish_at<=?) "
            "ORDER BY CASE WHEN publish_at='' THEN 0 ELSE 1 END, id ASC LIMIT 1",
            (now_str,),
        ).fetchone()
        if not row:
            return None
        conn().execute("UPDATE tasks SET status=1, attempts=attempts+1, updated_at=? WHERE id=?",
                       (_now(), row["id"]))
        conn().commit()
        return dict(row)


def cancel_task(task_id: int) -> None:
    _exec("UPDATE tasks SET status=5, updated_at=? WHERE id=? AND status=0", (_now(), task_id))


def reset_task(task_id: int) -> None:
    _exec("UPDATE tasks SET status=0, error='', updated_at=? WHERE id=? AND status IN (3,4,5)",
          (_now(), task_id))


def delete_task(task_id: int) -> None:
    _exec("DELETE FROM tasks WHERE id=?", (task_id,))


def clear_tasks(statuses: tuple[int, ...] = (2, 3, 4, 5)) -> int:
    marks = ",".join("?" * len(statuses))
    with _LOCK:
        cursor = conn().execute(f"DELETE FROM tasks WHERE status IN ({marks})", statuses)
        conn().commit()
        return cursor.rowcount


def task_counts() -> dict[str, int]:
    rows = _rows("SELECT status, COUNT(*) AS c FROM tasks GROUP BY status")
    counts = {TASK_STATUS[s]: 0 for s in TASK_STATUS}
    total = 0
    for row in rows:
        counts[TASK_STATUS.get(row["status"], "未知")] = row["c"]
        total += row["c"]
    counts["全部"] = total
    return counts


# --------------------------------------------------------------------------- 日志

def add_log(message: str, level: str = "INFO", source: str = "", task_id: int = 0) -> None:
    _exec(
        "INSERT INTO logs (ts, level, source, task_id, message) VALUES (?,?,?,?,?)",
        (_now(), level, source, task_id, message),
    )


def list_logs(limit: int = 300) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))


def clear_logs() -> None:
    _exec("DELETE FROM logs")


def prune_logs(keep: int = 3000) -> None:
    _exec(
        "DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT ?)",
        (keep,),
    )
