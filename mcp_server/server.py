# -*- coding: utf-8 -*-
"""MCP server：把四个平台的发布能力暴露成工具。

工具名统一 matrix_ 前缀，参数一律用平台 key（douyin/tencent/xhs/ks），
不用数字 id——模型更容易把 1/2/3/4 记混。
"""
from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import __version__, service

INSTRUCTIONS = """这是「视频矩阵分发」的本地发布工具，可以把本地视频文件发布到抖音、视频号、小红书、快手。

典型流程：
1. matrix_list_accounts 查看有哪些已登录账号（返回 account_id）
2. matrix_check_login 确认账号登录状态；返回 NEED_HUMAN_LOGIN 就调 matrix_login
3. matrix_publish 传 dry_run=true 先预演，检查参数与登录
4. matrix_publish 正式发布；单条会阻塞到出结果，超过等待时间会返回 TIMEOUT 和 task_id
5. matrix_task_status 查进度

注意事项：
- 发布是真实的外部动作，会产生公开内容，执行前请与用户确认标题、平台和账号。
- 四个平台共用同一个串行队列，不要并发发起多条；批量用 matrix_publish_batch。
- 返回 ok=false 时看 code：NEED_HUMAN_LOGIN 表示凭据失效，调 matrix_login 让用户扫码。
- 登录需要用户拿手机扫码：抖音/视频号/快手会弹出浏览器窗口显示二维码，小红书是本地
  二维码图片。扫码最长等 300 秒，AI 不要让用户"假设已经登录"。
- 不传 title 时用视频文件名；小红书必须有封面图。
"""

server = MCPServer(
    name="matrix-publisher",
    title="视频矩阵分发",
    description="把本地视频发布到抖音、视频号、小红书、快手（本地浏览器自动化）",
    version=__version__,
    instructions=INSTRUCTIONS,
)


@server.tool()
async def matrix_list_platforms() -> dict[str, Any]:
    """列出支持的平台及其 key、数字 id 和中文别名。

    发布相关工具都接受 key（douyin/tencent/xhs/ks）或中文名，不接受无意义的猜测值。
    """
    return await asyncio.to_thread(service.list_platforms)


@server.tool()
async def matrix_list_accounts(platform: str | None = None) -> dict[str, Any]:
    """列出已登录的发布账号。

    Args:
        platform: 可选，只看某个平台。取值 douyin / tencent / xhs / ks 或中文名。

    返回每个账号的 account_id、平台、昵称、登录状态，以及 cookie 是否存在。
    不返回任何凭据内容。account_id 是后续发布要用的标识。
    """
    return await asyncio.to_thread(service.list_accounts, platform)


@server.tool()
async def matrix_check_login(account_id: int) -> dict[str, Any]:
    """检查某个账号的登录是否仍然有效。

    Args:
        account_id: matrix_list_accounts 返回的账号 id。

    抖音/快手/视频号会真实打开无头浏览器验证，约 5-10 秒；小红书只校验本地凭据。
    返回 NEED_HUMAN_LOGIN 表示凭据已失效，接着调 matrix_login 让用户扫码续期。
    """
    return await asyncio.to_thread(service.check_login, account_id)


@server.tool()
async def matrix_login(
    platform: str | None = None,
    account_id: int | None = None,
    show_qrcode: bool = True,
) -> dict[str, Any]:
    """扫码登录一个平台账号。二维码会显示在本机屏幕上，需要用户拿手机扫。

    Args:
        platform: douyin / tencent / xhs / ks，或中文名。新建账号时必填。
        account_id: 已有账号的 id，重新登录（续期）时用这个。
        show_qrcode: 小红书等无窗口平台是否自动打开二维码图片，默认 true。

    抖音/视频号/快手会弹出真实浏览器窗口，二维码就在窗口里，请让用户直接扫；
    小红书没有浏览器窗口，二维码是本地图片，会自动用系统看图器打开。
    整个过程最长等 300 秒，期间不要重复调用。返回 ok=false 时看 code 与 error。
    """
    return await asyncio.to_thread(service.login, platform, account_id, show_qrcode)


@server.tool()
async def matrix_publish(
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
    timeout: int = 0,
) -> dict[str, Any]:
    """把一条本地视频发布到一个平台的账号。

    Args:
        platform: douyin / tencent / xhs / ks，或中文名。
        account_id: 目标账号 id（见 matrix_list_accounts）。
        video_path: 视频文件绝对路径，必须在允许目录内。
        title: 标题，留空则用文件名；超过 50 字会被截断。
        tags: 话题标签列表，不带 # 号。
        cover_path: 封面图路径，小红书必填。
        description: 正文描述（抖音/快手支持）。
        location: 位置，留空用默认位置。
        publish_at: 定时发布时间，格式 "YYYY-MM-DD HH:MM"，留空立即发布。
        dry_run: true 时只校验参数与登录，不真的发布。
        timeout: 等待秒数，0 表示用默认值（300 秒）。

    返回 ok=true 且 status=已成功 表示发布完成；TIMEOUT 表示仍在后台执行，
    用 matrix_task_status 继续查，不要重复提交。
    """
    return await asyncio.to_thread(
        service.publish,
        platform=platform,
        account_id=account_id,
        video_path=video_path,
        title=title,
        tags=tags,
        cover_path=cover_path,
        description=description,
        location=location,
        publish_at=publish_at,
        dry_run=dry_run,
        timeout=timeout,
    )


@server.tool()
async def matrix_publish_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
    """批量创建发布任务，立即返回 task_id，后台串行执行。

    Args:
        items: 任务列表，每项字段同 matrix_publish：
            platform, account_id, video_path, title, tags, cover_path,
            description, location, publish_at。

    返回 queued 数量、每个任务的 task_id，以及被拒绝的条目和原因。
    之后用 matrix_task_status 按 task_id 或 batch_id 查询进度。
    """
    return await asyncio.to_thread(service.publish_batch, items)


@server.tool()
async def matrix_task_status(
    task_id: int | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """查询发布任务的状态。

    Args:
        task_id: 单个任务 id。
        batch_id: 批次 id，返回该批次全部任务与完成数。

    两者至少提供一个。
    """
    return await asyncio.to_thread(service.task_status, task_id, batch_id)


@server.tool()
async def matrix_health() -> dict[str, Any]:
    """自检运行环境：数据目录、浏览器、账号数、队列状态。

    发布失败且原因不明时先调这个。chrome_ok=false 意味着没装系统 Chrome，
    视频号和小红书可能因为缺少 h264 支持而失败。
    """
    return await asyncio.to_thread(service.health)
