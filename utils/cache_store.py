# -*- coding: utf-8 -*-
"""缓存层。

原项目使用 Redis 存放登录二维码、扫码状态等临时数据。桌面客户端场景下
用户机器上不会有 Redis，因此这里提供一个同签名的本地实现（SQLite），
并通过环境变量 / 配置在两者之间切换，保证原服务器部署方式不受影响。

对外接口与原代码中重复定义的 cache_data / cache_get_data / cache_delete 完全一致：

    cache_data(key, value, timeout=60)
    cache_get_data(key) -> str
    cache_delete(key)

切换方式（优先级从高到低）：
    1. 环境变量 MATRIX_CACHE_BACKEND = "local" | "redis"
    2. conf.REDIS_CONF 中设置 "enabled": True/False
    3. 默认：尝试 Redis，连不上自动降级到本地
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_LOCAL_DB: Path | None = None
_BACKEND: str | None = None  # "redis" / "local"
_REDIS_CLIENT: Any = None


def _conf_redis() -> dict:
    try:
        from conf import REDIS_CONF  # noqa: WPS433
        return REDIS_CONF or {}
    except Exception:
        return {}


def _local_db_path() -> Path:
    """本地缓存放位置，跟随 BASE_DIR（桌面端会指向用户数据目录）。"""
    global _LOCAL_DB
    if _LOCAL_DB is not None:
        return _LOCAL_DB
    try:
        from conf import BASE_DIR  # noqa: WPS433
        base = Path(BASE_DIR)
    except Exception:
        base = Path.cwd()
    cache_dir = base / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    _LOCAL_DB = cache_dir / "kv_cache.db"
    return _LOCAL_DB


def _init_local() -> None:
    with _LOCK:
        conn = sqlite3.connect(_local_db_path(), timeout=10)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                " k TEXT PRIMARY KEY,"
                " v TEXT,"
                " expire_at REAL"
                ")"
            )
            conn.commit()
        finally:
            conn.close()


def _local_set(key: str, value: str, timeout: int) -> None:
    expire_at = time.time() + timeout if timeout else 0
    with _LOCK:
        conn = sqlite3.connect(_local_db_path(), timeout=10)
        try:
            conn.execute(
                "INSERT INTO kv (k, v, expire_at) VALUES (?,?,?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v, expire_at=excluded.expire_at",
                (key, value, expire_at),
            )
            conn.commit()
        finally:
            conn.close()


def _local_get(key: str) -> str:
    with _LOCK:
        conn = sqlite3.connect(_local_db_path(), timeout=10)
        try:
            row = conn.execute("SELECT v, expire_at FROM kv WHERE k=?", (key,)).fetchone()
        finally:
            conn.close()
    if not row:
        return ""
    value, expire_at = row
    if expire_at and time.time() > expire_at:
        _local_delete(key)
        return ""
    return value or ""


def _local_delete(key: str) -> None:
    with _LOCK:
        conn = sqlite3.connect(_local_db_path(), timeout=10)
        try:
            conn.execute("DELETE FROM kv WHERE k=?", (key,))
            conn.commit()
        finally:
            conn.close()


def _get_redis():
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    import redis  # noqa: WPS433

    conf = _conf_redis()
    kwargs = {
        "host": conf.get("host", "127.0.0.1"),
        "port": conf.get("port", 6379),
        "db": conf.get("select_db", 0),
        "socket_connect_timeout": 1,
        "socket_timeout": 3,
    }
    if conf.get("password"):
        kwargs["password"] = conf["password"]
    client = redis.Redis(**kwargs)
    client.ping()
    _REDIS_CLIENT = client
    return client


def _resolve_backend() -> str:
    """决定使用哪种后端，失败时静默降级。"""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    forced = (os.environ.get("MATRIX_CACHE_BACKEND") or "").strip().lower()
    conf = _conf_redis()
    if not forced:
        if conf.get("enabled") is False:
            forced = "local"
        elif conf.get("enabled") is True:
            forced = "redis"

    if forced == "local":
        _init_local()
        _BACKEND = "local"
        return _BACKEND

    try:
        _get_redis()
        _BACKEND = "redis"
    except Exception:
        _init_local()
        _BACKEND = "local"
    return _BACKEND


def reset_backend() -> None:
    """用于配置变更后重新探测后端。"""
    global _BACKEND, _REDIS_CLIENT
    _BACKEND = None
    _REDIS_CLIENT = None


def cache_data(key: str, value: str, timeout: int = 60) -> None:
    if _resolve_backend() == "redis":
        try:
            client = _get_redis()
            client.set(key, value)
            client.expire(key, timeout)
            return
        except Exception:
            reset_backend()
            _init_local()
    _local_set(key, value, timeout)


def cache_get_data(key: str) -> str:
    if _resolve_backend() == "redis":
        try:
            data = _get_redis().get(key)
            if data is None:
                return ""
            return data.decode("utf-8") if isinstance(data, bytes) else str(data)
        except Exception:
            reset_backend()
            _init_local()
    return _local_get(key)


def cache_delete(key: str) -> None:
    if _resolve_backend() == "redis":
        try:
            _get_redis().delete(key)
            return
        except Exception:
            reset_backend()
            _init_local()
    _local_delete(key)
