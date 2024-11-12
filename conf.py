from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
BASE_PATH = "D:\wwwroot\matrix\matrix\\" #按照自己电脑路径自己改后面会+path作为视频的完整路径，如果是linux类系统请将\改为/
XHS_SERVER = "http://127.0.0.1:5005"
REDIS_CONF = {
    "host":"127.0.0.1",
    "port":6379,
    "select_db":0,
    "password":""
}
MYSQL_CONF = {
    "host":"localhost",
    "port":3306,
    "database":"matrix",
    "username":"root",
    "password":"afUn8SqpOPNQ6nOR",
    "auto_commit":True
}