# -*- coding: utf-8 -*-
"""概览页：账号与任务总览、快捷入口。"""
from __future__ import annotations

import time
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core import database as db
from ..theme import COLORS, platform_color
from ..widgets.common import (
    TASK_STATUS_VARIANT,
    Card,
    CardTitle,
    MetricCard,
    PageHeader,
    StatusChip,
    make_platform_badge,
)


class DashboardPage(QWidget):
    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = PageHeader("概览", "视频矩阵内容分发 · 本机运行")
        publish_button = QPushButton("＋ 新建发布")
        publish_button.setObjectName("Primary")
        publish_button.setCursor(Qt.PointingHandCursor)
        publish_button.clicked.connect(lambda: self.navigate.emit("publish"))
        header.add_action(publish_button)
        layout.addWidget(header)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_accounts = MetricCard("可用账号", "0", COLORS["primary"])
        self.metric_waiting = MetricCard("等待发布", "0", COLORS["warning"])
        self.metric_today = MetricCard("今日成功", "0", COLORS["success"])
        self.metric_failed = MetricCard("失败 / 失效", "0", COLORS["danger"])
        for card in (
            self.metric_accounts, self.metric_waiting,
            self.metric_today, self.metric_failed,
        ):
            metrics.addWidget(card)
        layout.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(16)

        # 最近任务
        recent_card = Card(stretch=False)
        recent_card.add(CardTitle("最近任务"))
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(6)
        recent_card.add_layout(self.recent_box)
        recent_card.body().addStretch(1)
        body.addWidget(recent_card, 2)

        # 账号概况
        side = QVBoxLayout()
        side.setSpacing(16)

        account_card = Card()
        account_card.add(CardTitle("平台账号"))
        self.platform_box = QVBoxLayout()
        self.platform_box.setSpacing(10)
        account_card.add_layout(self.platform_box)
        side.addWidget(account_card)

        quick_card = Card()
        quick_card.add(CardTitle("快捷操作"))
        for text, page in (("管理账号", "accounts"), ("查看队列", "queue"), ("运行日志", "logs")):
            button = QPushButton(text)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(32)
            button.clicked.connect(lambda _=False, p=page: self.navigate.emit(p))
            quick_card.add(button)
        side.addWidget(quick_card)
        side.addStretch(1)

        body.addLayout(side, 1)
        layout.addLayout(body, 1)

    # ------------------------------------------------------------------ 数据
    def refresh(self) -> None:
        accounts = db.list_accounts()
        active = [a for a in accounts if a["status"] == 1]
        counts = db.task_counts()
        self.metric_accounts.set_value(len(active))
        self.metric_waiting.set_value(counts.get("等待中", 0) + counts.get("发布中", 0))
        self.metric_failed.set_value(counts.get("失败", 0) + counts.get("登录失效", 0))

        today_success = sum(
            1 for task in db.list_tasks(2, limit=500)
            if task["finished_at"] and date.fromtimestamp(task["finished_at"]) == date.today()
        )
        self.metric_today.set_value(today_success)

        # 最近任务
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        tasks = db.list_tasks(limit=6)
        if not tasks:
            empty = QLabel("暂无任务，点击右上角「新建发布」开始")
            empty.setObjectName("Empty")
            empty.setAlignment(Qt.AlignCenter)
            self.recent_box.addWidget(empty)
        else:
            for task in tasks:
                self.recent_box.addWidget(self._task_row(task))

        # 平台账号概况
        while self.platform_box.count():
            item = self.platform_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for platform, name in db.PLATFORMS.items():
            total = sum(1 for a in accounts if a["platform"] == platform)
            ok = sum(1 for a in active if a["platform"] == platform)
            self.platform_box.addWidget(self._platform_row(platform, name, ok, total))

    def _task_row(self, task: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(10)
        layout.addWidget(make_platform_badge(int(task["platform"]), 24))

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        title = QLabel((task["title"] or "(无标题)")[:34])
        title.setStyleSheet("font-size:13px;")
        subtitle = QLabel(
            f"{task.get('account_name') or '未知账号'} · "
            + (task["publish_at"] or "立即")
        )
        subtitle.setObjectName("Hint")
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        layout.addLayout(text_box)
        layout.addStretch(1)

        status_text, variant = TASK_STATUS_VARIANT.get(int(task["status"]), ("未知", "muted"))
        layout.addWidget(StatusChip(status_text, variant))
        return row

    def _platform_row(self, platform: int, name: str, ok: int, total: int) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        badge = QLabel()
        badge.setFixedSize(8, 8)
        badge.setStyleSheet(f"background:{platform_color(platform)}; border-radius:4px;")
        layout.addWidget(badge)
        layout.addWidget(QLabel(name))
        layout.addStretch(1)
        value = QLabel(f"{ok} / {total}")
        value.setStyleSheet(
            f"color:{COLORS['success'] if ok else COLORS['text_muted']}; font-weight:600;"
        )
        layout.addWidget(value)
        return row
