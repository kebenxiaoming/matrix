# -*- coding: utf-8 -*-
"""应用图标（运行时绘制，避免额外资源依赖）。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)


def _draw_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#6A72FF"))
    gradient.setColorAt(1.0, QColor("#4048C8"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.NoPen)
    radius = size * 0.26
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    # 播放三角
    margin = size * 0.30
    triangle = QPolygonF([
        QPointF(size * 0.40, margin),
        QPointF(size * 0.40, size - margin),
        QPointF(size - margin, size / 2),
    ])
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.drawPolygon(triangle)

    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_draw_pixmap(size))
    return icon


def save_ico(path: str) -> None:
    """导出 .ico 供打包使用（Qt 支持写 ico）。"""
    pixmap = _draw_pixmap(256)
    pixmap.save(path, "ICO")


def _arrow_image(direction: str, color: str = "#8A90A6", width: int = 18, height: int = 12) -> QImage:
    # 用 QImage 而非 QPixmap：QImage 不依赖 QGuiApplication，可在任意时机生成
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.NoPen)

    cx = width / 2
    half = min(width, height) * 0.30
    margin = (height - half) / 2
    if direction == "up":
        triangle = QPolygonF([
            QPointF(cx - half, height - margin),
            QPointF(cx + half, height - margin),
            QPointF(cx, margin),
        ])
    else:
        triangle = QPolygonF([
            QPointF(cx - half, margin),
            QPointF(cx + half, margin),
            QPointF(cx, height - margin),
        ])
    painter.drawPolygon(triangle)
    painter.end()
    return image


def ensure_ui_assets(ui_dir) -> None:
    """生成 QSS 需要的小图标（Qt 样式表无法用 CSS 画三角箭头）。"""
    from pathlib import Path

    directory = Path(ui_dir)
    directory.mkdir(parents=True, exist_ok=True)
    _arrow_image("up").save(str(directory / "arrow_up.png"), "PNG")
    _arrow_image("down").save(str(directory / "arrow_down.png"), "PNG")
