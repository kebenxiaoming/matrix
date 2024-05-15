from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
BASE_PATH = "D:/wwwroot/matrix-backend/storage/app/"
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
    "database":"quanke_matrix",
    "username":"root",
    "password":"afUn8SqpOPNQ6nOR",
    "auto_commit":True
}