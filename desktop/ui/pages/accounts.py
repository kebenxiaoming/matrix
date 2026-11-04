# -*- coding: utf-8 -*-
"""账号管理页：添加平台账号、扫码登录、查看状态。"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import database as db
from ...core.login_service import LoginWorker
from ..theme import COLORS
from ..widgets.common import (
    ACCOUNT_STATUS_VARIANT,
    Card,
    PageHeader,
    StatusChip,
    make_platform_badge,
)


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


class QRCodeDialog(QDialog):
    """小红书登录是纯接口扫码，没有浏览器窗口，二维码得由客户端弹出来。"""

    def __init__(self, image_path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("扫码登录小红书")
        self.setModal(False)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QLabel("请用小红书 App 扫描二维码")
        title.setStyleSheet("font-size:14px; font-weight:600;")
        layout.addWidget(title)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            image_label.setText("二维码加载失败，请查看运行日志")
        else:
            image_label.setPixmap(
                pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        layout.addWidget(image_label)

        hint = QLabel("二维码约 2 分钟有效；扫码成功后本窗口会自动关闭。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)


class AccountsPage(QWidget):
    accounts_changed = Signal()
    log = Signal(str, str)

    COLUMNS = ["账号", "平台", "状态", "最近登录", "操作"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._workers: dict[int, LoginWorker] = {}
        self._qr_dialogs: dict[int, QRCodeDialog] = {}
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = PageHeader("账号管理", "扫码登录各平台创作者账号，登录状态保存在本机")
        self.add_button = QPushButton("＋ 添加账号")
        self.add_button.setObjectName("Primary")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.clicked.connect(self._show_add_menu)
        header.add_action(self.add_button)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh)
        header.add_action(self.refresh_button)

        layout.addWidget(header)

        self.filter_box = QComboBox()
        self.filter_box.addItem("全部平台", 0)
        for pid, name in db.PLATFORMS.items():
            self.filter_box.addItem(name, pid)
        self.filter_box.setFixedWidth(140)
        self.filter_box.currentIndexChanged.connect(self.refresh)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("筛选"))
        filter_row.addWidget(self.filter_box)
        filter_row.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        filter_row.addWidget(self.count_label)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setDefaultSectionSize(58)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 190)
        layout.addWidget(self.table, 1)

        self.empty_label = QLabel("还没有账号，点击右上角「添加账号」开始扫码登录")
        self.empty_label.setObjectName("Empty")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        tip = QLabel("提示：登录时会弹出一个浏览器窗口，用手机对应 App 扫码即可。抖音登录后若提示身份验证，按浏览器内指引完成短信验证。")
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        layout.addWidget(tip)

    def _show_add_menu(self) -> None:
        menu = QMenu(self)
        for platform, name in db.PLATFORMS.items():
            action = menu.addAction(f"添加{name}账号")
            action.triggered.connect(lambda _=False, p=platform: self._add_account(p))
        menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft()))

    # ------------------------------------------------------------------ 数据
    def refresh(self) -> None:
        platform = self.filter_box.currentData() or None
        accounts = db.list_accounts(platform)

        self.table.setRowCount(0)
        for row, account in enumerate(accounts):
            self.table.insertRow(row)
            self._fill_row(row, account)

        has_data = bool(accounts)
        self.table.setVisible(has_data)
        self.empty_label.setVisible(not has_data)
        self.count_label.setText(f"共 {len(accounts)} 个账号" if has_data else "")

    def _fill_row(self, row: int, account: dict) -> None:
        platform = int(account["platform"])
        account_id = int(account["id"])

        name_widget = QWidget()
        name_layout = QHBoxLayout(name_widget)
        name_layout.setContentsMargins(8, 0, 0, 0)
        name_layout.setSpacing(10)
        name_layout.addWidget(make_platform_badge(platform, 30))
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        username = account["username"] or "未命名账号"
        title = QLabel(username)
        title.setStyleSheet("font-weight:600;")
        subtitle = QLabel(account["third_id"] or "尚未获取账号 ID")
        subtitle.setObjectName("Hint")
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        name_layout.addLayout(text_box)
        name_layout.addStretch(1)
        self.table.setCellWidget(row, 0, name_widget)

        platform_item = QTableWidgetItem(db.PLATFORMS.get(platform, "—"))
        platform_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, platform_item)

        status_text, variant = ACCOUNT_STATUS_VARIANT.get(int(account["status"]), ("未知", "muted"))
        chip = StatusChip(status_text, variant)
        chip_wrapper = QWidget()
        chip_layout = QHBoxLayout(chip_wrapper)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.addStretch(1)
        worker = self._workers.get(account_id)
        if worker is not None and worker.isRunning():
            chip.set_status("登录中…", "warning")
        chip_layout.addWidget(chip)
        chip_layout.addStretch(1)
        self.table.setCellWidget(row, 2, chip_wrapper)

        login_item = QTableWidgetItem(_fmt_ts(int(account["last_login_at"])))
        login_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, login_item)

        actions = QWidget()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(6, 0, 6, 0)
        action_layout.setSpacing(6)
        is_logging = worker is not None and worker.isRunning()

        login_btn = QPushButton("登录中…" if is_logging else ("重新登录" if account["status"] == 1 else "去登录"))
        login_btn.setObjectName("Ghost")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setEnabled(not is_logging)
        login_btn.clicked.connect(lambda _=False, a=account: self._start_login(a))
        action_layout.addWidget(login_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("Danger")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda _=False, a=account: self._delete_account(a))
        action_layout.addWidget(delete_btn)
        self.table.setCellWidget(row, 4, actions)

    # ------------------------------------------------------------------ 动作
    def _add_account(self, platform: int) -> None:
        account_id = db.create_account(platform)
        self.refresh()
        account = db.get_account(account_id)
        if account:
            self._start_login(account)

    def _start_login(self, account: dict) -> None:
        account_id = int(account["id"])
        existing = self._workers.get(account_id)
        if existing is not None and existing.isRunning():
            return

        worker = LoginWorker(account_id, int(account["platform"]))
        worker.log.connect(self.log.emit)
        worker.qrcode_ready.connect(self._show_qrcode)
        worker.succeeded.connect(self._on_login_ok)
        worker.failed.connect(self._on_login_fail)
        worker.finished.connect(lambda a=account_id: self._on_worker_done(a))
        self._workers[account_id] = worker
        worker.start()
        self.refresh()

    def _show_qrcode(self, account_id: int, image_path: str) -> None:
        self._close_qrcode(account_id)
        dialog = QRCodeDialog(image_path, self)
        dialog.finished.connect(lambda _=0, a=account_id: self._qr_dialogs.pop(a, None))
        dialog.show()
        dialog.raise_()
        self._qr_dialogs[account_id] = dialog

    def _close_qrcode(self, account_id: int) -> None:
        dialog = self._qr_dialogs.pop(account_id, None)
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def _on_login_ok(self, account_id: int, info: dict) -> None:
        self._close_qrcode(account_id)
        name = info.get("username") or info.get("account_id") or ""
        self.log.emit(f"账号登录成功：{name}", "INFO")
        db.add_log(f"账号登录成功：{name}", "INFO", "登录")
        self.refresh()
        self.accounts_changed.emit()

    def _on_login_fail(self, account_id: int, reason: str) -> None:
        self._close_qrcode(account_id)
        self.log.emit(f"账号登录失败：{reason}", "ERROR")
        db.add_log(f"账号登录失败：{reason}", "ERROR", "登录", account_id)
        self.refresh()
        # 登录失败必须让用户当场看到原因，否则只会看到"未登录"不知所措
        QMessageBox.warning(
            self,
            "登录未完成",
            f"{reason}\n\n可以再点一次「去登录」重试；详细过程见「运行日志」页。",
        )

    def _on_worker_done(self, account_id: int) -> None:
        self._close_qrcode(account_id)
        worker = self._workers.pop(account_id, None)
        if worker is not None:
            worker.deleteLater()
        self.refresh()

    def _delete_account(self, account: dict) -> None:
        answer = QMessageBox.question(
            self,
            "删除账号",
            f"确定删除「{account['username'] or account['third_id']}」吗？\n"
            "该账号未执行的发布任务也会一并删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        db.delete_account(int(account["id"]))
        self.log.emit("账号已删除", "WARN")
        self.refresh()
        self.accounts_changed.emit()

    def has_running_login(self) -> bool:
        return any(worker.isRunning() for worker in self._workers.values())
