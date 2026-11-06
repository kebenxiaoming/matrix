# -*- coding: utf-8 -*-
"""诊断：按钮背景色与表单行高度问题。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import (
    QApplication, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from desktop.ui.theme import STYLE_SHEET

app = QApplication(sys.argv)


class Card(QWidget):
    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 18, 18, 18)
        self.lay.setSpacing(12)


window = QWidget()
window.resize(760, 420)
outer = QVBoxLayout(window)
outer.setSpacing(16)

# 1. 主按钮
primary = QPushButton("＋ 新建发布")
primary.setObjectName("Primary")
primary.setCursor(primary.cursor())
outer.addWidget(primary)

# 2. QFormLayout 版本
card_a = Card()
form = QFormLayout()
form.setSpacing(12)
edit = QLineEdit("重庆市")
spin = QSpinBox()
spin.setRange(0, 600)
form.addRow("默认定位城市", edit)
form.addRow("任务间隔", spin)
card_a.lay.addLayout(form)
outer.addWidget(card_a)

# 3. 手写行版本
card_b = Card()


def row(label, widget):
    holder = QWidget()
    h = QHBoxLayout(holder)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(12)
    tag = QLabel(label)
    tag.setFixedWidth(110)
    tag.setSizePolicy(tag.sizePolicy().horizontalPolicy(), tag.sizePolicy().verticalPolicy())
    h.addWidget(tag)
    h.addWidget(widget, 1)
    return holder


card_b.lay.addWidget(row("默认定位城市", QLineEdit("重庆市")))
card_b.lay.addWidget(row("任务间隔", QSpinBox()))
outer.addWidget(card_b)

outer.addStretch(1)

app.setStyleSheet(STYLE_SHEET)
window.show()
app.processEvents()

print("primary size:", primary.size(), "sizeHint:", primary.sizeHint())
print("primary palette btn:", primary.palette().button().color().name())
print("edit size:", edit.size(), "sizeHint:", edit.sizeHint())
print("card_a size:", card_a.size(), "hint:", card_a.sizeHint())
print("form size:", form.sizeHint())

window.grab().save(str(Path(__file__).parent / "shots" / "diag.png"))
print("saved diag.png")
