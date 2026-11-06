# -*- coding: utf-8 -*-
"""生成应用图标文件（打包用）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from desktop.ui.icon import save_ico

target = ROOT / "desktop" / "resources" / "app.ico"
target.parent.mkdir(parents=True, exist_ok=True)
save_ico(str(target))
print("icon ->", target, target.exists(), target.stat().st_size if target.exists() else 0)
