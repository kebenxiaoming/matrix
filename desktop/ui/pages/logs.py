# -*- coding: utf-8 -*-
"""运行日志页。"""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core import database as db
from ...core import paths
from ..widgets.common import PageHeader

MAX_LINES = 2000


class LogsPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()
        self.load_history()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = PageHeader("运行日志", "记录登录、发布和队列的实时运行情况")
        self.autoscroll_box = QPushButton("自动滚动：开")
        self.autoscroll_box.setCheckable(True)
        self.autoscroll_box.setChecked(True)
        self.autoscroll_box.setCursor(Qt.PointingHandCursor)
        self.autoscroll_box.toggled.connect(self._toggle_autoscroll)
        header.add_action(self.autoscroll_box)

        export_button = QPushButton("导出")
        export_button.clicked.connect(self._export)
        header.add_action(export_button)

        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self._clear)
        header.add_action(clear_button)

        layout.addWidget(header)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(MAX_LINES)
        self.view.setStyleSheet(
            "QPlainTextEdit{background:#14161F; color:#D8DCE6;"
            "border:none; border-radius:10px; padding:12px;"
            "font-family:Consolas,'Cascadia Mono','Microsoft YaHei UI',monospace; font-size:12px;}"
        )
        layout.addWidget(self.view, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------ 内容
    def load_history(self) -> None:
        self.view.clear()
        for row in reversed(db.list_logs(400)):
            ts = datetime.fromtimestamp(row["ts"]).strftime("%m-%d %H:%M:%S")
            level = row["level"]
            source = f"[{row['source']}] " if row["source"] else ""
            self._append_line(ts, level, f"{source}{row['message']}")
        self._scroll_to_end()

    def append(self, message: str, level: str = "INFO") -> None:
        ts = time.strftime("%H:%M:%S")
        self._append_line(ts, level, message)
        if self.autoscroll_box.isChecked():
            self._scroll_to_end()

    def _append_line(self, ts: str, level: str, message: str) -> None:
        self.view.appendPlainText(f"{ts}  {level:<5} {message}")
        self.status_label.setText(f"共 {self.view.blockCount()} 行")

    def _scroll_to_end(self) -> None:
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _toggle_autoscroll(self, checked: bool) -> None:
        self.autoscroll_box.setText(f"自动滚动：{'开' if checked else '关'}")
        if checked:
            self._scroll_to_end()

    def _clear(self) -> None:
        self.view.clear()
        db.clear_logs()
        self.status_label.setText("共 0 行")

    def _export(self) -> None:
        default = paths.logs_dir() / f"matrix-log-{time.strftime('%Y%m%d-%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", str(default), "文本文件 (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.view.toPlainText())
            QMessageBox.information(self, "导出成功", f"日志已保存到：\n{path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(exc))
