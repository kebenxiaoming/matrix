# -*- coding: utf-8 -*-
"""通用界面组件。"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme import COLORS, PLATFORM_SHORT, platform_color


class Card(QFrame):
    """白底圆角卡片。

    内容默认靠顶部排列（末尾有 stretch），避免父布局空间变大时
    内部控件被均匀拉开。需要内容撑满的卡片可传 stretch=False。
    """

    def __init__(self, parent: QWidget | None = None, padding: int = 18,
                 spacing: int = 12, stretch: bool = True):
        super().__init__(parent)
        self.setObjectName("Card")
        self._stretch = stretch
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(spacing)
        if stretch:
            self._layout.addStretch(1)

    # 兼容旧写法：直接对布局操作
    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget) -> QWidget:
        self._insert_widget(widget)
        return widget

    def add_layout(self, layout) -> None:
        if self._stretch:
            self._pop_stretch()
        self._layout.addLayout(layout)
        if self._stretch:
            self._layout.addStretch(1)

    def add_widget_stretch(self, widget: QWidget) -> QWidget:
        """需要占满剩余空间的控件（例如表格、滚动区）。"""
        if self._stretch:
            self._pop_stretch()
        self._layout.addWidget(widget, 1)
        if self._stretch:
            self._layout.addStretch(1)
        return widget

    def _insert_widget(self, widget: QWidget) -> None:
        if self._stretch:
            self._pop_stretch()
        self._layout.addWidget(widget)
        if self._stretch:
            self._layout.addStretch(1)

    def _pop_stretch(self) -> None:
        count = self._layout.count()
        if count:
            item = self._layout.itemAt(count - 1)
            if item is not None and item.spacerItem() is not None:
                self._layout.takeAt(count - 1)


class CardTitle(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("CardTitle")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)


class FormRow(QWidget):
    """一行表单：左标签 + 右控件。比 QFormLayout 的高度计算更稳定。"""

    def __init__(self, label: str, widget: QWidget, label_width: int = 128,
                 parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        tag = QLabel(label)
        tag.setObjectName("SectionLabel")
        tag.setFixedWidth(label_width)
        tag.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(tag)

        widget.setMinimumHeight(34)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(widget, 1)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.field = widget


class CheckMark(QWidget):
    """自绘勾选框：QSS 无法绘制对勾，这里直接画笔绘制，保证选中态清晰。"""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, size: int = 18, parent: QWidget | None = None):
        super().__init__(parent)
        self._checked = checked
        self._size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = bool(checked)
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event) -> None:  # noqa: D102
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: D102
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size = self._size
        rect = QRectF(1, 1, size - 2, size - 2)

        if self._checked:
            painter.setBrush(QBrush(QColor(COLORS["primary"])))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 4, 4)

            pen = QPen(QColor("#FFFFFF"), 2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(size * 0.27, size * 0.53)
            path.lineTo(size * 0.44, size * 0.70)
            path.lineTo(size * 0.75, size * 0.32)
            painter.drawPath(path)
        else:
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(QPen(QColor("#D1D5DB"), 1))
            painter.drawRoundedRect(rect, 4, 4)
        painter.end()


def make_platform_badge(platform: int, size: int = 28) -> QLabel:
    """生成平台首字圆形徽标。"""
    label = QLabel()
    label.setFixedSize(size, size)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor(platform_color(platform))))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    font = QFont()
    font.setPixelSize(int(size * 0.5))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QPen(QColor("#FFFFFF")))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, PLATFORM_SHORT.get(platform, "?"))
    painter.end()
    label.setPixmap(pixmap)
    return label


class StatusChip(QLabel):
    """状态标签：彩色圆点 + 文案。"""

    VARIANTS = {
        "success": (COLORS["success"], COLORS["success_light"]),
        "warning": (COLORS["warning"], COLORS["warning_light"]),
        "danger": (COLORS["danger"], COLORS["danger_light"]),
        "info": (COLORS["primary"], COLORS["primary_light"]),
        "muted": (COLORS["text_muted"], "#F3F4F6"),
    }

    def __init__(self, text: str = "", variant: str = "muted", parent: QWidget | None = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.set_status(text, variant)

    def set_status(self, text: str, variant: str = "muted") -> None:
        fg, bg = self.VARIANTS.get(variant, self.VARIANTS["muted"])
        self.setText(text)
        self.setStyleSheet(
            f"color:{fg}; background:{bg}; border-radius:9px;"
            f"padding:2px 10px; font-size:11px; font-weight:600;"
        )


TASK_STATUS_VARIANT = {
    0: ("等待中", "info"),
    1: ("发布中", "warning"),
    2: ("已成功", "success"),
    3: ("失败", "danger"),
    4: ("登录失效", "danger"),
    5: ("已取消", "muted"),
}

ACCOUNT_STATUS_VARIANT = {
    0: ("未登录", "muted"),
    1: ("正常", "success"),
    2: ("已失效", "danger"),
}


class PageHeader(QWidget):
    """页面标题区。"""

    def __init__(self, title: str, desc: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        text_wrapper = QWidget()
        text_wrapper.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        text_box = QVBoxLayout(text_wrapper)
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        text_box.addWidget(title_label)
        if desc:
            desc_label = QLabel(desc)
            desc_label.setObjectName("PageDesc")
            desc_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            text_box.addWidget(desc_label)
        text_box.addStretch(1)
        layout.addWidget(text_wrapper)
        layout.addStretch(1)

        self._right = QHBoxLayout()
        self._right.setSpacing(8)
        self._right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(self._right)

    def add_action(self, widget: QWidget) -> QWidget:
        widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._right.addWidget(widget, 0, Qt.AlignVCenter)
        return widget


class MetricCard(QFrame):
    """统计数字卡片。"""

    def __init__(self, label: str, value: str = "0", color: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if color:
            self.value_label.setStyleSheet(f"color:{color};")

        self.label_widget = QLabel(label)
        self.label_widget.setObjectName("MetricLabel")
        self.label_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout.addWidget(self.value_label)
        layout.addWidget(self.label_widget)
        layout.addStretch(1)

    def set_value(self, value) -> None:
        self.value_label.setText(str(value))


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{COLORS['border']}; border:none;")
    return line


def icon_size(size: int = 16) -> QSize:
    return QSize(size, size)
