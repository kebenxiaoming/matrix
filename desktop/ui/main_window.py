# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 内容区。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..core import config, database as db, paths
from .icon import app_icon
from .pages.accounts import AccountsPage
from .pages.dashboard import DashboardPage
from .pages.logs import LogsPage
from .pages.publish import PublishPage
from .pages.queue import QueuePage
from .pages.settings import SettingsPage
from .theme import COLORS

NAV_ITEMS = [
    ("dashboard", "概览"),
    ("accounts", "账号管理"),
    ("publish", "新建发布"),
    ("queue", "发布队列"),
    ("logs", "运行日志"),
    ("settings", "设置"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频矩阵分发客户端")
        self.setWindowIcon(app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(1000, 660)

        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._build()

        self._tray = self._build_tray()
        self._switch_page("dashboard")
        self._append_log("客户端已启动，数据目录：" + str(paths.data_root()), "INFO")

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentStack")
        layout.addWidget(self.stack, 1)

        self.dashboard_page = DashboardPage()
        self.accounts_page = AccountsPage()
        self.publish_page = PublishPage()
        self.queue_page = QueuePage()
        self.logs_page = LogsPage()
        self.settings_page = SettingsPage()

        for key, widget in (
            ("dashboard", self.dashboard_page),
            ("accounts", self.accounts_page),
            ("publish", self.publish_page),
            ("queue", self.queue_page),
            ("logs", self.logs_page),
            ("settings", self.settings_page),
        ):
            self._pages[key] = widget
            self.stack.addWidget(widget)

        self._wire_signals()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(196)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(4)

        brand = QLabel("视频矩阵分发")
        brand.setObjectName("BrandTitle")
        layout.addWidget(brand)
        brand_sub = QLabel("Matrix Publisher  v1.0")
        brand_sub.setObjectName("BrandSub")
        layout.addWidget(brand_sub)
        layout.addSpacing(20)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(38)
            button.clicked.connect(lambda _=False, k=key: self._switch_page(k))
            group.addButton(button)
            self._nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)

        self.queue_state = QLabel("队列未运行")
        self.queue_state.setObjectName("SidebarFooter")
        layout.addWidget(self.queue_state)

        version = QLabel("本地运行 · 数据不上传")
        version.setObjectName("SidebarFooter")
        layout.addWidget(version)
        return sidebar

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(app_icon(), self)
        tray.setToolTip("视频矩阵分发客户端")
        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._restore_window)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    # ------------------------------------------------------------------ 信号
    def _wire_signals(self) -> None:
        self.dashboard_page.navigate.connect(self._switch_page)

        self.accounts_page.log.connect(self._append_log)
        self.accounts_page.accounts_changed.connect(self._on_accounts_changed)

        self.publish_page.log.connect(self._append_log)
        self.publish_page.tasks_created.connect(self._on_tasks_created)

        self.queue_page.log.connect(self._append_log)
        self.queue_page.worker_state_changed.connect(self._on_queue_state)

        self.settings_page.log.connect(self._append_log)
        self.settings_page.settings_saved.connect(self._on_settings_saved)

    def _append_log(self, message: str, level: str = "INFO") -> None:
        self.logs_page.append(message, level)

    def _on_accounts_changed(self) -> None:
        self.publish_page.refresh_accounts()
        self.dashboard_page.refresh()

    def _on_tasks_created(self, count: int) -> None:
        self.queue_page.refresh()
        self.dashboard_page.refresh()
        self._switch_page("queue")

    def _on_queue_state(self, running: bool) -> None:
        self.queue_state.setText("队列运行中…" if running else "队列未运行")
        self.queue_state.setStyleSheet(
            f"color:{COLORS['success']}; font-size:11px;" if running
            else "color:#6E7488; font-size:11px;"
        )

    def _on_settings_saved(self) -> None:
        try:
            from ..core import xhs_signer

            xhs_signer.install(config.get("xhs_signer", "local"))
        except Exception:
            pass

    # ------------------------------------------------------------------ 导航
    def _switch_page(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        for name, button in self._nav_buttons.items():
            button.setChecked(name == key)

        if key == "dashboard":
            self.dashboard_page.refresh()
        elif key == "accounts":
            self.accounts_page.refresh()
        elif key == "publish":
            self.publish_page.refresh_accounts()
        elif key == "queue":
            self.queue_page.refresh()
        elif key == "logs":
            self.logs_page.load_history()

    # ------------------------------------------------------------------ 托盘
    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_window()

    def _restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self) -> None:
        self._tray.hide()
        self.close()

    # ------------------------------------------------------------------ 关闭
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: D102
        busy = self.queue_page.is_running() or self.accounts_page.has_running_login()
        if busy:
            answer = QMessageBox.question(
                self,
                "仍有任务在执行",
                "队列或登录任务仍在运行，退出会中断正在进行的发布。确定退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return

        if config.get("close_to_tray") and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage("视频矩阵分发", "已最小化到托盘", QSystemTrayIcon.Information, 2000)
            return

        self.queue_page.shutdown()
        try:
            from ..core import xhs_signer

            xhs_signer.shutdown()
        except Exception:
            pass
        db.close()
        event.accept()
