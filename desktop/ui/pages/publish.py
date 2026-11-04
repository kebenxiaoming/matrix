# -*- coding: utf-8 -*-
"""新建发布页：选择素材、填写内容、勾选目标账号，生成发布任务。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core import config
from ...core import database as db
from ..theme import COLORS
from ..widgets.common import Card, CardTitle, CheckMark, PageHeader, make_platform_badge

VIDEO_FILTER = "视频文件 (*.mp4 *.mov *.mkv *.avi *.flv *.wmv *.m4v);;所有文件 (*.*)"
IMAGE_FILTER = "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp);;所有文件 (*.*)"

# 这些平台必须提供封面，否则上传流程会失败
COVER_REQUIRED = {2, 3, 4}


class DropZone(QFrame):
    """可点击 / 可拖拽的文件选择区。"""

    file_selected = Signal(str)

    def __init__(self, title: str, hint: str, filters: str, parent=None):
        super().__init__(parent)
        self._filters = filters
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(76)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QFrame {{ border:1px dashed #CBD2E0; border-radius:10px; background:#FBFCFE; }}"
            f"QFrame:hover {{ border-color:{COLORS['primary']}; background:{COLORS['primary_light']}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:600; border:none; background:transparent;")
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("Hint")
        self.hint_label.setStyleSheet("border:none; background:transparent;")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.hint_label)

    def set_value(self, path: str) -> None:
        if path:
            name = Path(path).name
            self.title_label.setText(f"✓ {name}")
            self.title_label.setStyleSheet(
                f"font-weight:600; color:{COLORS['success']}; border:none; background:transparent;"
            )
            self.hint_label.setText(str(Path(path).parent))
            self.setToolTip(path)
        else:
            self.title_label.setStyleSheet("font-weight:600; border:none; background:transparent;")
            self.setToolTip("")

    def mousePressEvent(self, event) -> None:  # noqa: D102
        if event.button() == Qt.LeftButton:
            path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", self._filters)
            if path:
                self.set_value(path)
                self.file_selected.emit(path)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: D102
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: D102
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.set_value(path)
                self.file_selected.emit(path)
                break
        event.acceptProposedAction()


class AccountCheckRow(QWidget):
    def __init__(self, account: dict, parent=None):
        super().__init__(parent)
        self.account_id = int(account["id"])
        self.platform = int(account["platform"])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)
        self.checkbox = CheckMark(account.get("status") == 1)
        self.checkbox.setEnabled(account.get("status") == 1)
        layout.addWidget(self.checkbox)
        layout.addWidget(make_platform_badge(self.platform, 22))
        name = QLabel(account["username"] or f"账号 {account['id']}")
        name.setStyleSheet("font-size:12px;")
        layout.addWidget(name)
        if account.get("status") != 1:
            warn = QLabel("未登录")
            warn.setStyleSheet(f"color:{COLORS['danger']}; font-size:11px;")
            layout.addWidget(warn)
        layout.addStretch(1)


class PublishPage(QWidget):
    tasks_created = Signal(int)   # 新建任务数量
    log = Signal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._video_path = ""
        self._cover_path = ""
        self._rows: list[AccountCheckRow] = []
        self._build()
        self.refresh_accounts()

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        header = PageHeader("新建发布", "一次填写，同时分发到多个平台账号")
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        content = QWidget()
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 6, 0)
        columns.setSpacing(16)

        # ---------------- 左列：素材与内容
        left = QVBoxLayout()
        left.setSpacing(12)

        material_card = Card(padding=16, spacing=10)
        material_card.add(CardTitle("素材"))
        self.video_zone = DropZone("点击选择视频，或把视频拖到这里", "支持 mp4 / mov / mkv 等常见格式", VIDEO_FILTER)
        self.video_zone.file_selected.connect(self._on_video_selected)
        material_card.add(self.video_zone)
        self.cover_zone = DropZone(
            "选择封面图（视频号 / 快手 / 小红书必填）",
            "建议使用与视频画面一致的竖版图片",
            IMAGE_FILTER,
        )
        self.cover_zone.file_selected.connect(self._on_cover_selected)
        material_card.add(self.cover_zone)
        left.addWidget(material_card)

        form_card = Card(padding=16, spacing=10)
        form_card.add(CardTitle("内容"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("作品标题（抖音/快手最多 30 字，超出会自动截断）")
        self.title_edit.setMaxLength(120)
        form_card.add(self._labeled("标题", self.title_edit))

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("话题标签，用空格分隔，例如：日常 vlog 重庆")
        form_card.add(self._labeled("话题标签", self.tags_edit))

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("作品描述（仅小红书使用，留空则与标题相同）")
        form_card.add(self._labeled("描述", self.desc_edit))

        self.location_edit = QLineEdit(config.get("default_location", ""))
        self.location_edit.setPlaceholderText("定位城市，例如：重庆市")
        form_card.add(self._labeled("定位", self.location_edit))
        left.addWidget(form_card)

        schedule_card = Card(padding=16, spacing=10)
        schedule_card.add(CardTitle("发布时机"))
        schedule_row = QWidget()
        schedule_layout = QHBoxLayout(schedule_row)
        schedule_layout.setContentsMargins(0, 0, 0, 0)
        schedule_layout.setSpacing(9)
        self.schedule_check = CheckMark(False)
        self.schedule_check.toggled.connect(self._toggle_schedule)
        schedule_layout.addWidget(self.schedule_check)
        schedule_layout.addWidget(QLabel("定时发布（不勾选则进入队列后立即发布）"))
        schedule_layout.addStretch(1)
        schedule_card.add(schedule_row)
        self.schedule_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.schedule_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.schedule_edit.setCalendarPopup(True)
        self.schedule_edit.setEnabled(False)
        self.schedule_edit.setMinimumDateTime(QDateTime.currentDateTime())
        schedule_card.add(self._labeled("发布时间", self.schedule_edit))
        left.addWidget(schedule_card)
        left.addStretch(1)

        # ---------------- 右列：账号选择
        right_card = Card(stretch=False)
        right_header = QHBoxLayout()
        right_header.setSpacing(4)
        right_header.addWidget(CardTitle("发布到哪些账号"))
        right_header.addStretch(1)
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setObjectName("Ghost")
        self.select_all_btn.setCursor(Qt.PointingHandCursor)
        self.select_all_btn.clicked.connect(lambda: self._toggle_all(True))
        right_header.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton("清空")
        self.select_none_btn.setObjectName("Ghost")
        self.select_none_btn.setCursor(Qt.PointingHandCursor)
        self.select_none_btn.clicked.connect(lambda: self._toggle_all(False))
        right_header.addWidget(self.select_none_btn)
        right_card.add_layout(right_header)

        self.account_box = QVBoxLayout()
        self.account_box.setSpacing(2)
        account_container = QWidget()
        account_container.setLayout(self.account_box)
        self.account_scroll = QScrollArea()
        self.account_scroll.setWidgetResizable(True)
        self.account_scroll.setFrameShape(QFrame.NoFrame)
        self.account_scroll.setMinimumHeight(200)
        self.account_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self.account_scroll.setWidget(account_container)
        right_card.add_widget_stretch(self.account_scroll)

        self.account_empty = QLabel("还没有可用账号\n请先到「账号管理」添加并登录")
        self.account_empty.setObjectName("Empty")
        self.account_empty.setAlignment(Qt.AlignCenter)
        self.account_empty.setWordWrap(True)
        self.account_empty.setMinimumHeight(160)
        right_card.add_widget_stretch(self.account_empty)

        self.submit_button = QPushButton("加入发布队列")
        self.submit_button.setObjectName("Primary")
        self.submit_button.setMinimumHeight(40)
        self.submit_button.setCursor(Qt.PointingHandCursor)
        self.submit_button.clicked.connect(self._submit)
        right_card.add(self.submit_button)
        right_card.setMinimumWidth(360)
        right_card.setMaximumWidth(420)
        right_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        columns.addLayout(left, 1)
        columns.addWidget(right_card, 0)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def _labeled(self, label: str, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        tag = QLabel(label)
        tag.setObjectName("SectionLabel")
        layout.addWidget(tag)
        layout.addWidget(widget)
        return wrapper

    # ------------------------------------------------------------------ 账号
    def refresh_accounts(self) -> None:
        while self.account_box.count():
            item = self.account_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

        accounts = [a for a in db.list_accounts() if a["status"] == 1]
        self.account_empty.setVisible(not accounts)
        self.account_scroll.setVisible(bool(accounts))
        if not accounts:
            return

        current_platform = None
        for account in accounts:
            platform = int(account["platform"])
            if platform != current_platform:
                current_platform = platform
                section = QLabel(db.PLATFORMS.get(platform, ""))
                section.setObjectName("SectionLabel")
                section.setStyleSheet(
                    f"color:{COLORS['text_secondary']}; font-size:11px;"
                    "margin-top:8px; font-weight:600;"
                )
                self.account_box.addWidget(section)
            row = AccountCheckRow(account)
            self._rows.append(row)
            self.account_box.addWidget(row)
        self.account_box.addStretch(1)

    def _toggle_all(self, checked: bool) -> None:
        for row in self._rows:
            if row.checkbox.isEnabled():
                row.checkbox.setChecked(checked)

    def _selected_accounts(self) -> list[AccountCheckRow]:
        return [row for row in self._rows if row.checkbox.isChecked()]

    # ------------------------------------------------------------------ 交互
    def _on_video_selected(self, path: str) -> None:
        self._video_path = path
        if not self.title_edit.text().strip():
            self.title_edit.setText(Path(path).stem[:30])

    def _on_cover_selected(self, path: str) -> None:
        self._cover_path = path

    def _toggle_schedule(self, checked: bool) -> None:
        self.schedule_edit.setEnabled(checked)

    # ------------------------------------------------------------------ 提交
    def _submit(self) -> None:
        if not self._video_path or not Path(self._video_path).exists():
            QMessageBox.warning(self, "缺少视频", "请先选择要发布的视频文件。")
            return

        selected = self._selected_accounts()
        if not selected:
            QMessageBox.warning(self, "未选择账号", "请至少勾选一个发布账号。")
            return

        needs_cover = {row.platform for row in selected} & COVER_REQUIRED
        if needs_cover and (not self._cover_path or not Path(self._cover_path).exists()):
            names = "、".join(db.PLATFORMS.get(p, "") for p in sorted(needs_cover))
            QMessageBox.warning(
                self, "缺少封面",
                f"{names} 发布时必须提供封面图，请先选择封面。",
            )
            return

        publish_at = ""
        if self.schedule_check.isChecked():
            publish_at = self.schedule_edit.dateTime().toString("yyyy-MM-dd HH:mm")
            if self.schedule_edit.dateTime() <= QDateTime.currentDateTime():
                QMessageBox.warning(self, "时间无效", "定时发布时间需要晚于当前时间。")
                return

        payload = {
            "title": self.title_edit.text().strip() or Path(self._video_path).stem[:30],
            "description": self.desc_edit.text().strip(),
            "tags": self.tags_edit.text().strip(),
            "video_path": self._video_path,
            "cover_path": self._cover_path,
            "location": self.location_edit.text().strip(),
            "publish_at": publish_at,
        }
        count = db.create_tasks([row.account_id for row in selected], payload)
        db.add_log(f"新建 {count} 条发布任务：{payload['title']}", "INFO", "发布")
        self.log.emit(f"已创建 {count} 条发布任务", "INFO")
        self.tasks_created.emit(count)
        self._reset_form()
        QMessageBox.information(
            self, "已加入队列",
            f"已创建 {count} 条发布任务。\n"
            + ("到达设定时间后会自动发布。" if publish_at else "队列运行中会立即开始发布。"),
        )

    def _reset_form(self) -> None:
        self._video_path = ""
        self._cover_path = ""
        self.video_zone.set_value("")
        self.video_zone.title_label.setText("点击选择视频，或把视频拖到这里")
        self.cover_zone.set_value("")
        self.cover_zone.title_label.setText("选择封面图（视频号 / 快手 / 小红书必填）")
        self.title_edit.clear()
        self.tags_edit.clear()
        self.desc_edit.clear()
        self.schedule_check.setChecked(False)
