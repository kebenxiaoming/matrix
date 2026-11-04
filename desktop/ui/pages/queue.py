# -*- coding: utf-8 -*-
"""发布队列页：查看任务状态、启停队列、重试失败任务。"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import database as db
from ...core.publish_service import PublishWorker
from ..theme import COLORS
from ..widgets.common import (
    TASK_STATUS_VARIANT,
    MetricCard,
    PageHeader,
    StatusChip,
    make_platform_badge,
)


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "—"
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


class QueuePage(QWidget):
    log = Signal(str, str)
    worker_state_changed = Signal(bool)

    COLUMNS = ["状态", "平台", "账号", "标题", "计划时间", "完成时间", "操作"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.worker: PublishWorker | None = None
        self._build()

        self.timer = QTimer(self)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = PageHeader("发布队列", "队列按创建顺序串行执行，定时任务到点后才会出队")
        self.start_button = QPushButton("▶ 启动队列")
        self.start_button.setObjectName("Primary")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self.start_queue)
        header.add_action(self.start_button)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        header.add_action(self.pause_button)

        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_queue)
        header.add_action(self.stop_button)

        layout.addWidget(header)

        # 统计卡片
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_waiting = MetricCard("等待中", "0", COLORS["primary"])
        self.metric_running = MetricCard("发布中", "0", COLORS["warning"])
        self.metric_success = MetricCard("已成功", "0", COLORS["success"])
        self.metric_failed = MetricCard("失败 / 失效", "0", COLORS["danger"])
        for card in (self.metric_waiting, self.metric_running, self.metric_success, self.metric_failed):
            metrics.addWidget(card)
        layout.addLayout(metrics)

        # 筛选栏
        filter_row = QHBoxLayout()
        self.filter_box = QComboBox()
        self.filter_box.addItem("全部状态", -1)
        for status, name in db.TASK_STATUS.items():
            self.filter_box.addItem(name, status)
        self.filter_box.setFixedWidth(140)
        self.filter_box.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.filter_box)
        filter_row.addStretch(1)
        self.clear_button = QPushButton("清空已完成")
        self.clear_button.clicked.connect(self._clear_finished)
        filter_row.addWidget(self.clear_button)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(50)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.Fixed)
        header_view.setSectionResizeMode(5, QHeaderView.Fixed)
        header_view.setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 160)
        layout.addWidget(self.table, 1)

        self.empty_label = QLabel("队列是空的，去「新建发布」添加任务吧")
        self.empty_label.setObjectName("Empty")
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label, 1)

    # ------------------------------------------------------------------ 队列控制
    def start_queue(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.worker = PublishWorker()
        self.worker.log.connect(self.log.emit)
        self.worker.task_started.connect(lambda _id: self.refresh())
        self.worker.task_finished.connect(lambda *_: self.refresh())
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("暂停")
        self.stop_button.setEnabled(True)
        self.worker_state_changed.emit(True)
        self.log.emit("队列已启动", "INFO")

    def toggle_pause(self) -> None:
        if self.worker is None:
            return
        if self.worker.paused:
            self.worker.resume()
            self.pause_button.setText("暂停")
            self.log.emit("队列已恢复", "INFO")
        else:
            self.worker.pause()
            self.pause_button.setText("继续")
            self.log.emit("队列已暂停（当前任务会执行完）", "WARN")

    def stop_queue(self) -> None:
        if self.worker is None:
            return
        self.log.emit("正在停止队列，等待当前任务结束…", "WARN")
        self.worker.stop()
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)

    def _on_worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("暂停")
        self.stop_button.setEnabled(False)
        self.worker_state_changed.emit(False)
        self.refresh()

    def is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def shutdown(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(8000)

    # ------------------------------------------------------------------ 渲染
    def refresh(self) -> None:
        counts = db.task_counts()
        self.metric_waiting.set_value(counts.get("等待中", 0))
        self.metric_running.set_value(counts.get("发布中", 0))
        self.metric_success.set_value(counts.get("已成功", 0))
        self.metric_failed.set_value(counts.get("失败", 0) + counts.get("登录失效", 0))

        status = self.filter_box.currentData()
        tasks = db.list_tasks(None if status == -1 else status, limit=300)

        selected = self._selected_task_id()
        self.table.setRowCount(0)
        for row, task in enumerate(tasks):
            self.table.insertRow(row)
            self._fill_row(row, task)
        if selected:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 3)
                if item is not None and item.data(Qt.UserRole) == selected:
                    self.table.selectRow(row)
                    break

        has_data = bool(tasks)
        self.table.setVisible(has_data)
        self.empty_label.setVisible(not has_data)

    def _selected_task_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 3)
        return item.data(Qt.UserRole) if item else None

    def _fill_row(self, row: int, task: dict) -> None:
        status = int(task["status"])
        text, variant = TASK_STATUS_VARIANT.get(status, ("未知", "muted"))
        chip = StatusChip(text, variant)
        chip_wrapper = QWidget()
        chip_layout = QHBoxLayout(chip_wrapper)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.addWidget(chip)
        self.table.setCellWidget(row, 0, chip_wrapper)

        platform = int(task["platform"])
        badge = make_platform_badge(platform, 22)
        badge_wrapper = QWidget()
        badge_layout = QHBoxLayout(badge_wrapper)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.addWidget(badge)
        self.table.setCellWidget(row, 1, badge_wrapper)

        account_name = task.get("account_name") or f"账号{task['account_id']}"
        account_item = QTableWidgetItem(account_name)
        account_item.setToolTip(account_name)
        self.table.setItem(row, 2, account_item)

        title_item = QTableWidgetItem(task["title"] or "(无标题)")
        title_item.setData(Qt.UserRole, int(task["id"]))
        title_item.setToolTip(f"{task['title']}\n{task['video_path']}\n{task.get('error') or ''}")
        self.table.setItem(row, 3, title_item)

        plan = task["publish_at"] or "立即"
        self.table.setItem(row, 4, QTableWidgetItem(plan))
        self.table.setItem(row, 5, QTableWidgetItem(_fmt_ts(int(task["finished_at"]))))

        actions = QWidget()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(4, 0, 4, 0)
        action_layout.setSpacing(4)

        if status == 0:
            cancel_btn = QPushButton("取消")
            cancel_btn.setObjectName("Link")
            cancel_btn.clicked.connect(lambda _=False, t=task: self._cancel(t))
            action_layout.addWidget(cancel_btn)
        elif status in (3, 4, 5):
            retry_btn = QPushButton("重试")
            retry_btn.setObjectName("Link")
            retry_btn.clicked.connect(lambda _=False, t=task: self._retry(t))
            action_layout.addWidget(retry_btn)

        if status in (2, 3, 4, 5):
            del_btn = QPushButton("删除")
            del_btn.setObjectName("Link")
            del_btn.clicked.connect(lambda _=False, t=task: self._delete(t))
            action_layout.addWidget(del_btn)

        action_layout.addStretch(1)
        self.table.setCellWidget(row, 6, actions)

    # ------------------------------------------------------------------ 动作
    def _cancel(self, task: dict) -> None:
        db.cancel_task(int(task["id"]))
        self.refresh()

    def _retry(self, task: dict) -> None:
        db.reset_task(int(task["id"]))
        db.update_task(int(task["id"]), attempts=0)
        self.log.emit(f"任务 #{task['id']} 已重新入队", "INFO")
        self.refresh()

    def _delete(self, task: dict) -> None:
        db.delete_task(int(task["id"]))
        self.refresh()

    def _clear_finished(self) -> None:
        count = db.clear_tasks()
        if count:
            self.log.emit(f"已清理 {count} 条已完成任务", "INFO")
        self.refresh()
