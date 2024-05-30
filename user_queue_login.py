import argparse
import time
import asyncio
import pymysql
from pathlib import Path
from conf import BASE_DIR,MYSQL_CONF
from douyin_uploader.main import douyin_setup
from tencent_uploader.main import weixin_setup
from xhs_uploader.main import xhs_setup
from ks_uploader.main import ks_setup

parser = argparse.ArgumentParser(description='这是一个获取登录状态的脚本。') 
parser.add_argument('type', type=int, default=1, help='登录类型:1:抖音;2:视频号;3:小红书;4:快手')
args = parser.parse_args()
type = args.type
error_num = 1
# 创建mysql连接 TODO 待优化
db_connector = pymysql.connect(  
    host=MYSQL_CONF['host'],
    port=MYSQL_CONF['port'],
    user=MYSQL_CONF['username'],
    password=MYSQL_CONF['password'],
    database=MYSQL_CONF['database'],
    autocommit=MYSQL_CONF['auto_commit'],
)
#查询数据库处理
while True:
    try: 
        with db_connector.cursor() as mycursor:
            # 执行查询语句  
            mycursor.execute("SELECT id,uid,type FROM mx_account_login_queue WHERE status=0 AND type="f"{type}")  
            # 获取查询结果
            print("执行一次查询")
            for x in mycursor.fetchall():
                print(f"执行ID为{x[0]}的数据")
                # 更新数据
                mycursor.execute(f"UPDATE mx_account_login_queue SET status=1 WHERE id={x[0]}")
                # 处理登录
                queue_id = x[0]
                account_id = x[1]
                if x[2] == 1:
                    account_file_path = Path(BASE_DIR / "douyin_uploader"/ "account")
                    cookie_setup = asyncio.run(douyin_setup(str(account_file_path), handle=True,account_id=account_id,queue_id=queue_id))
                if x[2] == 2:
                    account_file_path = Path(BASE_DIR / "tencent_uploader"/ "account")
                    cookie_setup = asyncio.run(weixin_setup(str(account_file_path), handle=True,account_id=account_id,queue_id=queue_id))
                if x[2] == 3:
                    account_file_path = Path(BASE_DIR / "xhs_uploader"/ "account")
                    cookie_setup = xhs_setup(str(account_file_path), handle=True,account_id=account_id,queue_id=queue_id)
                if x[2] == 4:
                    account_file_path = Path(BASE_DIR / "ks_uploader"/ "account")
                    cookie_setup = asyncio.run(ks_setup(str(account_file_path), handle=True,account_id=account_id,queue_id=queue_id))
                if cookie_setup:
                    # 成功更新数据
                    mycursor.execute(f"UPDATE mx_account_login_queue SET status=2 WHERE id={x[0]}")
                    # 插入用户表数据
                    # 先判断当前用户的此条记录是否存在，不存在则插入
                    mycursor.execute(f"SELECT id,status,username,avatar FROM mx_account_info WHERE uid={account_id} AND account_id='{cookie_setup['account_id']}'")  
                    exist_info = mycursor.fetchone()
                    if not exist_info:
                        mycursor.execute(f"INSERT INTO mx_account_info (queue_id,uid,account_id,username,avatar,extend,type,status,created_at) VALUES ({queue_id},{account_id},'{cookie_setup['account_id']}','{cookie_setup['username']}','{cookie_setup['avatar']}','',{type},1,{int(time.time())})")
                    else:
                        # 存在则判断是否登录，未登录则改为登录
                        if exist_info[1] !=1:
                            if exist_info[2] != cookie_setup['username'] or exist_info[3] != cookie_setup['avatar']:
                                mycursor.execute(f"UPDATE mx_account_info SET status=1,username='{cookie_setup['username']}',avatar='{cookie_setup['avatar']}' WHERE id={exist_info[0]}")
                            else:
                                mycursor.execute(f"UPDATE mx_account_info SET status=1 WHERE id={exist_info[0]}")
                        else:
                            if exist_info[2] != cookie_setup['username'] or exist_info[3] != cookie_setup['avatar']:
                                mycursor.execute(f"UPDATE mx_account_info SET username='{cookie_setup['username']}',avatar='{cookie_setup['avatar']}' WHERE id={exist_info[0]}")
                else:
                    # 失败更新数据
                    mycursor.execute(f"UPDATE mx_account_login_queue SET status=3 WHERE id={x[0]}")  
    except db_connector.Error as err:
        # 更新为失败
        # raise err
        mycursor.execute(f"UPDATE mx_account_login_queue SET status=3 WHERE id={x[0]}") 
        print(f"Error: {err}") 
        error_num+=1
    except BaseException as err:
        # raise err
        print(f"Error: {err}")
        # 更新为失败
        mycursor.execute(f"UPDATE mx_account_login_queue SET status=3 WHERE id={x[0]}")  
        error_num+=1
    #错误超过10次则退出脚本
    if error_num > 10:
        break
    time.sleep(5)
db_connector.close()
