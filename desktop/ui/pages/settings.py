# -*- coding: utf-8 -*-
"""设置页：运行参数、平台通道、环境自检。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core import config, paths
from ..widgets.common import Card, CardTitle, FormRow, PageHeader, StatusChip, hline


class SettingsPage(QWidget):
    log = Signal(str, str)
    settings_saved = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()
        self._load_values()
        self._detect_env()

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        header = PageHeader("设置", "调整发布默认值与运行参数")
        save_button = QPushButton("保存设置")
        save_button.setObjectName("Primary")
        save_button.setCursor(Qt.PointingHandCursor)
        save_button.clicked.connect(self._save)
        header.add_action(save_button)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        content = QWidget()
        content.setObjectName("SettingsContent")
        content.setStyleSheet(
            "QWidget#SettingsContent { background: transparent; }"
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        # ---------------- 发布默认值
        publish_card = Card()
        publish_card.add(CardTitle("发布默认值"))

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("例如：重庆市")
        publish_card.add(FormRow("默认定位城市", self.location_edit))

        self.gap_spin = QSpinBox()
        self.gap_spin.setRange(0, 600)
        self.gap_spin.setSuffix(" 秒")
        publish_card.add(FormRow("任务间隔", self.gap_spin))

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 5)
        self.retry_spin.setSuffix(" 次")
        publish_card.add(FormRow("失败重试", self.retry_spin))

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(2, 120)
        self.interval_spin.setSuffix(" 秒")
        publish_card.add(FormRow("空闲轮询间隔", self.interval_spin))

        hint = QLabel("任务间隔用于避免短时间内连续操作被平台判定为异常，建议不低于 20 秒。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        publish_card.add(hint)
        layout.addWidget(publish_card)

        # ---------------- 平台
        platform_card = Card()
        platform_card.add(CardTitle("平台"))

        self.channel_box = QComboBox()
        self.channel_box.addItem("自动检测（推荐）", "")
        self.channel_box.addItem("使用系统 Chrome", "chrome")
        self.channel_box.addItem("使用内置 Chromium", "none")
        platform_card.add(FormRow("视频号浏览器", self.channel_box))

        self.signer_box = QComboBox()
        self.signer_box.addItem("内置签名（推荐）", "local")
        self.signer_box.addItem("外部签名服务", "server")
        platform_card.add(FormRow("小红书签名", self.signer_box))

        self.signer_url = QLineEdit()
        self.signer_url.setPlaceholderText("http://127.0.0.1:5005")
        platform_card.add(FormRow("签名服务地址", self.signer_url))

        channel_hint = QLabel(
            "视频号对视频编码有要求，使用系统 Chrome 成功率更高；"
            "小红书「外部签名服务」需要自行启动 xhs-api 的 Flask 服务。"
        )
        channel_hint.setObjectName("Hint")
        channel_hint.setWordWrap(True)
        platform_card.add(channel_hint)
        layout.addWidget(platform_card)

        # ---------------- 环境自检
        env_card = Card()
        env_card.add(CardTitle("环境自检"))
        self.chromium_chip = self._env_row(env_card, "内置 Chromium")
        self.chrome_chip = self._env_row(env_card, "系统 Chrome（视频号）")
        self.data_chip = self._env_row(env_card, "数据目录")

        env_card.add(hline())
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        open_data = QPushButton("打开数据目录")
        open_data.setMinimumHeight(32)
        open_data.clicked.connect(lambda: self._open_path(paths.data_root()))
        button_row.addWidget(open_data)
        open_logs = QPushButton("打开日志目录")
        open_logs.setMinimumHeight(32)
        open_logs.clicked.connect(lambda: self._open_path(paths.logs_dir()))
        button_row.addWidget(open_logs)
        button_row.addStretch(1)
        recheck = QPushButton("重新检测")
        recheck.setMinimumHeight(32)
        recheck.clicked.connect(self._detect_env)
        button_row.addWidget(recheck)
        env_card.add_layout(button_row)
        layout.addWidget(env_card)

        # ---------------- 关于
        about_card = Card()
        about_card.add(CardTitle("关于"))
        about_text = QLabel(
            "视频矩阵分发客户端 · 基于原 matrix 项目封装\n"
            f"版本 1.0.0　|　Python {sys.version.split()[0]}　|　数据保存在本机\n"
            "仅供个人学习与自有账号内容分发使用，请遵守各平台规则。"
        )
        about_text.setObjectName("Hint")
        about_text.setWordWrap(True)
        about_card.add(about_text)
        layout.addWidget(about_card)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def _env_row(self, card: Card, label: str) -> StatusChip:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        name = QLabel(label)
        name.setObjectName("SectionLabel")
        row.addWidget(name)
        row.addStretch(1)
        chip = StatusChip("检测中…", "muted")
        row.addWidget(chip)
        card.add(row_widget)
        return chip

    # ------------------------------------------------------------------ 数据
    def _load_values(self) -> None:
        self.location_edit.setText(config.get("default_location", ""))
        self.gap_spin.setValue(int(config.get("task_gap", 30)))
        self.retry_spin.setValue(int(config.get("retry_times", 1)))
        self.interval_spin.setValue(int(config.get("queue_interval", 5)))

        channel = config.get("tencent_channel", "")
        index = self.channel_box.findData(channel)
        self.channel_box.setCurrentIndex(index if index >= 0 else 0)

        signer = config.get("xhs_signer", "local")
        index = self.signer_box.findData(signer)
        self.signer_box.setCurrentIndex(index if index >= 0 else 0)
        self.signer_url.setText(config.get("xhs_server", ""))
        self.signer_box.currentIndexChanged.connect(self._sync_signer_state)
        self._sync_signer_state()

    def _sync_signer_state(self) -> None:
        self.signer_url.setEnabled(self.signer_box.currentData() == "server")

    def _save(self) -> None:
        config.update({
            "default_location": self.location_edit.text().strip(),
            "task_gap": self.gap_spin.value(),
            "retry_times": self.retry_spin.value(),
            "queue_interval": self.interval_spin.value(),
            "tencent_channel": self.channel_box.currentData(),
            "xhs_signer": self.signer_box.currentData(),
            "xhs_server": self.signer_url.text().strip(),
        })
        self.settings_saved.emit()
        self.log.emit("设置已保存", "INFO")
        QMessageBox.information(self, "已保存", "设置已保存。部分设置将在下次启动队列时生效。")

    # ------------------------------------------------------------------ 环境
    def _detect_env(self) -> None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                exe = Path(playwright.chromium.executable_path)
            if exe.exists():
                self.chromium_chip.set_status("已就绪", "success")
                self.chromium_chip.setToolTip(str(exe))
            else:
                self.chromium_chip.set_status("未安装", "danger")
                self.chromium_chip.setToolTip(f"缺少浏览器：{exe}")
        except Exception as exc:  # noqa: BLE001
            self.chromium_chip.set_status("异常", "danger")
            self.chromium_chip.setToolTip(str(exc))

        candidates = [
            Path(os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")),
            Path(os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")),
            Path(os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")),
        ]
        found = next((path for path in candidates if path.exists()), None)
        if found:
            self.chrome_chip.set_status("已安装", "success")
            self.chrome_chip.setToolTip(str(found))
        else:
            self.chrome_chip.set_status("未安装，视频号用内置浏览器", "warning")

        data_path = str(paths.data_root())
        short = data_path if len(data_path) <= 42 else "…" + data_path[-40:]
        self.data_chip.set_status(short, "info")
        self.data_chip.setToolTip(data_path)

    def _open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "无法打开", str(exc))
