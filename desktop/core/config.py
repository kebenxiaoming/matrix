# -*- coding: utf-8 -*-
"""应用配置：以 JSON 存放在数据目录下。"""
from __future__ import annotations

import copy
import json
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    # 发布默认值
    "default_location": "重庆市",
    "default_description": "",
    # 行为
    "show_browser": True,          # 发布时是否显示浏览器窗口
    "queue_interval": 5,           # 队列轮询间隔（秒）
    "task_gap": 30,                # 两个任务之间的间隔（秒），防止动作过快被风控
    "retry_times": 1,              # 失败重试次数
    "schedule_tolerance_minutes": 1,  # 定时发布允许提前触发的时间窗口
    # 平台
    "tencent_channel": "",         # 视频号浏览器通道：空=自动检测系统 Chrome
    "xhs_signer": "local",         # 小红书签名方式：local=进程内签名, server=外部服务
    "xhs_server": "http://127.0.0.1:5005",
    # 界面
    "minimize_to_tray": True,
    "close_to_tray": False,
    "run_on_startup": False,
}

_cache: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    data = copy.deepcopy(DEFAULTS)
    path = paths.config_path()
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except Exception:
            pass
    _cache = data
    return _cache


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, DEFAULTS.get(key, default))


def set(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    save()


def update(values: dict[str, Any]) -> None:
    data = _load()
    data.update({k: v for k, v in values.items() if k in DEFAULTS})
    save()


def all_values() -> dict[str, Any]:
    return dict(_load())


def save() -> None:
    if _cache is None:
        return
    path = paths.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def reload() -> None:
    global _cache
    _cache = None
    _load()
