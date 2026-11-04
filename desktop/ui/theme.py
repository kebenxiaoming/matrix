# -*- coding: utf-8 -*-
"""界面配色与全局样式表。"""
from __future__ import annotations

COLORS = {
    "primary": "#4F5BD5",
    "primary_hover": "#414CBB",
    "primary_light": "#EEF0FF",
    "success": "#16A34A",
    "success_light": "#E8F7EE",
    "warning": "#F59E0B",
    "warning_light": "#FEF6E7",
    "danger": "#DC2626",
    "danger_light": "#FDECEC",
    "text": "#1F2937",
    "text_secondary": "#6B7280",
    "text_muted": "#9CA3AF",
    "border": "#E5E7EB",
    "bg": "#F6F7F9",
    "card": "#FFFFFF",
    "sidebar": "#1E2130",
    "sidebar_hover": "#2A2E42",
    "sidebar_active": "#4F5BD5",
}

PLATFORM_COLORS = {
    1: "#FE2C55",  # 抖音
    2: "#07C160",  # 视频号
    3: "#FF2442",  # 小红书
    4: "#FF6600",  # 快手
}

PLATFORM_SHORT = {1: "抖", 2: "视", 3: "红", 4: "快"}


def platform_color(platform: int) -> str:
    return PLATFORM_COLORS.get(platform, COLORS["primary"])


STYLE_SHEET = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif;
}}

QWidget {{
    color: {COLORS['text']};
    font-size: 13px;
}}

QMainWindow, #RootWidget, #ContentStack {{
    background: {COLORS['bg']};
}}

/* ---------------------------------------------------------------- 侧边栏 */
#Sidebar {{
    background: {COLORS['sidebar']};
    border: none;
}}
#BrandTitle {{
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 600;
}}
#BrandSub {{
    color: #8A90A6;
    font-size: 11px;
}}
#NavButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #B9BECC;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
}}
#NavButton:hover {{
    background: {COLORS['sidebar_hover']};
    color: #FFFFFF;
}}
#NavButton:checked {{
    background: {COLORS['sidebar_active']};
    color: #FFFFFF;
    font-weight: 600;
}}
#SidebarFooter {{
    color: #6E7488;
    font-size: 11px;
}}

/* ---------------------------------------------------------------- 卡片 */
#Card {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}
#CardTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS['text']};
}}
#PageTitle {{
    font-size: 20px;
    font-weight: 600;
}}
#PageDesc {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
}}
#SectionLabel {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
}}
#MetricValue {{
    font-size: 26px;
    font-weight: 600;
}}
#MetricLabel {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
}}
#Hint {{
    color: {COLORS['text_muted']};
    font-size: 11px;
}}
#Empty {{
    color: {COLORS['text_muted']};
    font-size: 13px;
}}

/* ---------------------------------------------------------------- 按钮 */
QPushButton {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 7px 16px;
    color: {COLORS['text']};
}}
QPushButton:hover {{
    border-color: {COLORS['primary']};
    color: {COLORS['primary']};
}}
QPushButton:pressed {{
    background: {COLORS['primary_light']};
}}
QPushButton:disabled {{
    color: {COLORS['text_muted']};
    border-color: {COLORS['border']};
    background: #FAFAFB;
}}
QPushButton#Primary {{
    background: {COLORS['primary']};
    border: 1px solid {COLORS['primary']};
    color: #FFFFFF;
    font-weight: 600;
    padding: 8px 20px;
}}
QPushButton#Primary:hover {{
    background: {COLORS['primary_hover']};
    border-color: {COLORS['primary_hover']};
    color: #FFFFFF;
}}
QPushButton#Primary:disabled {{
    background: #C7CBF0;
    border-color: #C7CBF0;
    color: #FFFFFF;
}}
QPushButton#Danger {{
    color: {COLORS['danger']};
    border-color: #F3C6C6;
}}
QPushButton#Danger:hover {{
    background: {COLORS['danger_light']};
    border-color: {COLORS['danger']};
}}
QPushButton#Ghost {{
    background: transparent;
    border: none;
    color: {COLORS['primary']};
    padding: 4px 8px;
}}
QPushButton#Ghost:hover {{
    color: {COLORS['primary_hover']};
    text-decoration: underline;
}}
QPushButton#Link {{
    background: transparent;
    border: none;
    color: {COLORS['text_secondary']};
    padding: 2px 4px;
}}
QPushButton#Link:hover {{
    color: {COLORS['primary']};
}}

/* ---------------------------------------------------------------- 输入 */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDateTimeEdit, QComboBox {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {COLORS['primary']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus {{
    border-color: {COLORS['primary']};
}}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
    background: #F3F4F6;
    color: {COLORS['text_muted']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: url(__ARROW_DOWN__);
    width: 9px;
    height: 6px;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    background: {COLORS['card']};
    selection-background-color: {COLORS['primary_light']};
    selection-color: {COLORS['text']};
    padding: 4px;
    outline: none;
}}

QSpinBox, QDateTimeEdit {{
    padding-right: 22px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    background: transparent;
    border: none;
    width: 20px;
    subcontrol-origin: border;
}}
QSpinBox::up-button, QDateTimeEdit::up-button {{
    subcontrol-position: top right;
    margin: 4px 4px 0 0;
}}
QSpinBox::down-button, QDateTimeEdit::down-button {{
    subcontrol-position: bottom right;
    margin: 0 4px 4px 0;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDateTimeEdit::up-button:hover, QDateTimeEdit::down-button:hover {{
    background: {COLORS['primary_light']};
    border-radius: 4px;
}}
QSpinBox::up-arrow, QDateTimeEdit::up-arrow {{
    image: url(__ARROW_UP__);
    width: 9px;
    height: 6px;
}}
QSpinBox::down-arrow, QDateTimeEdit::down-arrow {{
    image: url(__ARROW_DOWN__);
    width: 9px;
    height: 6px;
}}
QDateTimeEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    border: none;
    background: transparent;
}}

QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #D1D5DB;
    border-radius: 4px;
    background: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background: {COLORS['primary']};
    border-color: {COLORS['primary']};
    image: none;
}}
QCheckBox::indicator:hover {{
    border-color: {COLORS['primary']};
}}

/* ---------------------------------------------------------------- 列表/表格 */
QTableWidget, QTableView {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    gridline-color: #F1F2F4;
    selection-background-color: {COLORS['primary_light']};
    selection-color: {COLORS['text']};
    outline: none;
}}
QTableWidget::item, QTableView::item {{
    padding: 6px;
    border-bottom: 1px solid #F5F6F8;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {COLORS['primary_light']};
    color: {COLORS['text']};
}}
QHeaderView::section {{
    background: #FAFBFC;
    color: {COLORS['text_secondary']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 9px 6px;
    font-size: 12px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: #FAFBFC;
    border: none;
}}

/* ---------------------------------------------------------------- 滚动条 */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #D5D8DE;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #BFC4CC;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #D5D8DE;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ---------------------------------------------------------------- 其他 */
QTextBrowser, QListWidget {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background: {COLORS['primary_light']};
    color: {COLORS['text']};
}}
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 14px;
    background: {COLORS['card']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {COLORS['text_secondary']};
}}
QSplitter::handle {{
    background: transparent;
}}
QToolTip {{
    background: #2B2F3A;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
}}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background: #EDEFF3;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {COLORS['primary']};
    border-radius: 4px;
}}
QMenu {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 22px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {COLORS['primary_light']};
}}
"""


def build_style_sheet(ui_dir=None) -> str:
    """把箭头图标的实际路径替换进样式表。

    Qt 样式表无法用 CSS 画三角，必须给 image 一个真实文件路径；
    图标由 icon.ensure_ui_assets() 在运行时生成到数据目录。
    """
    sheet = STYLE_SHEET
    if ui_dir:
        from pathlib import Path

        directory = Path(ui_dir)
        up = (directory / "arrow_up.png").as_posix()
        down = (directory / "arrow_down.png").as_posix()
        sheet = sheet.replace("__ARROW_UP__", up).replace("__ARROW_DOWN__", down)
    return sheet.replace("url(__ARROW_UP__)", "none").replace("url(__ARROW_DOWN__)", "none")
