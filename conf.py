import os
from pathlib import Path

# BASE_DIR 支持被桌面客户端重定向到用户数据目录（打包后代码目录是只读的）
BASE_DIR = Path(os.environ.get("MATRIX_BASE_DIR") or Path(__file__).parent.resolve())

# 视频等素材的根路径；桌面客户端改为直接存绝对路径，此配置仅兼容原有脚本
BASE_PATH = os.environ.get("MATRIX_BASE_PATH") or "D:\\wwwroot\\matrix\\matrix\\"

# 小红书签名服务地址，桌面客户端会在进程内启动该服务并注入实际端口
XHS_SERVER = os.environ.get("MATRIX_XHS_SERVER") or "http://127.0.0.1:5005"

# enabled: None = 自动探测（连得上 Redis 就用，否则用本地 SQLite 缓存）
#          True  = 强制使用 Redis
#          False = 强制使用本地缓存
REDIS_CONF = {
    "enabled": None,
    "host": "127.0.0.1",
    "port": 6379,
    "select_db": 0,
    "password": ""
}

# 仅在原服务器部署的队列脚本中使用
MYSQL_CONF = {
    "host": "localhost",
    "port": 3306,
    "database": "matrix",
    "username": "root",
    "password": "afUn8SqpOPNQ6nOR",
    "auto_commit": True
}
