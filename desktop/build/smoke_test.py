# -*- coding: utf-8 -*-
"""带测试数据的界面渲染 + 数据层校验。"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 使用独立数据目录，避免污染项目 data/
DATA_DIR = Path(tempfile.gettempdir()) / "matrix_smoke"
if DATA_DIR.exists():
    import shutil

    shutil.rmtree(DATA_DIR, ignore_errors=True)
os.environ["MATRIX_DATA_DIR"] = str(DATA_DIR)

OUT = Path(__file__).parent / "shots"
OUT.mkdir(exist_ok=True)

from desktop.core import paths

paths.prepare_runtime()

from desktop.core import database as db

# ---------------------------------------------------------------- 数据层校验
account_ids = []
for platform, third_id, username in (
    (1, "dy_1001", "山城小面探店"),
    (2, "sph_2002", "山城小面"),
    (3, "xhs_3003", "小面日记"),
    (4, "ks_4004", "重庆小面哥"),
):
    aid = db.create_account(platform)
    db.save_account_login(aid, third_id, username, "", str(DATA_DIR / f"cookie_{aid}.json"))
    account_ids.append(aid)

print("accounts:", [(a["id"], a["platform"], a["username"], a["status"]) for a in db.list_accounts()])

# 幂等校验：同平台同账号重复登录不应产生新行
before = len(db.list_accounts())
dup = db.create_account(1)
db.save_account_login(dup, "dy_1001", "山城小面探店", "", "x.json")
after = len(db.list_accounts())
print(f"dedupe check: before={before} after={after} (expect equal)")

# 任务
payload = {
    "title": "重庆这条老街的小面，一天只卖200碗",
    "description": "街边美食记录",
    "tags": "重庆 小面 美食探店",
    "video_path": str(DATA_DIR / "demo.mp4"),
    "cover_path": str(DATA_DIR / "demo.jpg"),
    "location": "重庆市",
    "publish_at": "",
}
now = int(time.time())
created = db.create_tasks(account_ids[:3], payload)
print("tasks created:", created)
db.create_tasks([account_ids[0]], {**payload, "title": "明天的定时视频", "publish_at": "2026-11-05 09:30"})

# 造几条不同状态
tasks = db.list_tasks()
if tasks:
    db.update_task(tasks[0]["id"], status=2, finished_at=now)
    db.update_task(tasks[1]["id"], status=3, error="登录已失效，请重新扫码登录", finished_at=now)

print("counts:", db.task_counts())
claimed = db.claim_next_task()
print("claim_next_task ->", claimed["id"] if claimed else None, claimed["status"] if claimed else None)

db.add_log("客户端已启动", "INFO", "系统")
db.add_log("账号登录成功：山城小面探店", "INFO", "登录")

# ---------------------------------------------------------------- 界面渲染
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop.ui.icon import app_icon, ensure_ui_assets
from desktop.ui.theme import build_style_sheet

app = QApplication(sys.argv)
app.setWindowIcon(app_icon())

ui_assets = paths.data_root() / ".ui"
ensure_ui_assets(ui_assets)
app.setStyleSheet(build_style_sheet(ui_assets))

from desktop.ui.main_window import MainWindow

window = MainWindow()
window.resize(1180, 780)
window.show()


def shoot():
    for key in ["dashboard", "accounts", "publish", "queue", "logs", "settings"]:
        window._switch_page(key)
        app.processEvents()
        window.grab().save(str(OUT / f"{key}.png"))
        print(f"saved {key}.png")
    app.quit()


QTimer.singleShot(800, shoot)
sys.exit(app.exec())
