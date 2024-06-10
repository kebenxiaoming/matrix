# import argparse
import time
import asyncio
import os
import pymysql
import traceback  
import redis
from pathlib import Path
from conf import BASE_DIR,BASE_PATH,MYSQL_CONF,REDIS_CONF
from datetime import datetime
from playwright.sync_api import sync_playwright
from tencent_uploader.main import TencentVideo
from douyin_uploader.main import DouYinVideo
from ks_uploader.main import KuaiShouVideo
from requests import RequestException
from xhs import XhsClient,exception as xhs_exception
from xhs_uploader.main import upload_xhs_video,sign
from utils.files_times import get_data_hashtags

# parser = argparse.ArgumentParser(description='这是一个上传视频的脚本。') 
# parser.add_argument('type', type=int, default=1, help='登录类型:1:抖音;2:视频号')
# args = parser.parse_args()
# type = args.type
error_num = 1
def cache_delete(key:str)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.delete(key)

def get_file_absolute_path(path:str):
    all_path = f"{BASE_PATH}{path}"
    return all_path

def deleteFile(account_file,type,account_uid,account_third_id):
    if os.path.exists(account_file):
        try:
            os.remove(account_file)  
            if type == 1:
                cache_delete(f"douyin_login_status_third_{account_uid}_{account_third_id}")
            elif type == 2:
                cache_delete(f"tencent_login_status_third_{account_uid}_{account_third_id}")
            elif type == 3:
                cache_delete(f"xhs_login_status_third_{account_uid}_{account_third_id}")
            print("文件已成功删除。")  
        except OSError as e:  
            print("删除文件时出错：", e)
            return False
        return True
# 抖音cookie校验
def douyin_cookie_auth(account_file,type,account_uid,account_third_id):
    if not os.path.exists(account_file):
        return False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page =context.new_page()
        # 访问指定的 URL
        page.goto("https://creator.douyin.com/creator-micro/content/upload")
        try:
            page.wait_for_selector("div.boards-more h3:text('抖音排行榜')", timeout=5000)  # 等待5秒
            print("[+] 等待5秒 cookie 失效")
            #失效直接删除json文件
            deleteFile(account_file,type,account_uid,account_third_id)
            context.close()
            browser.close()
            playwright.stop()
            return False
        except:
            print("[+] cookie 有效")
            context.close()
            browser.close()
            playwright.stop()
            return True

def ks_cookie_auth(account_file,type,account_uid,account_third_id):
    if not os.path.exists(account_file):
        return False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page =context.new_page()
        # 访问指定的 URL
        page.goto("https://cp.kuaishou.com/profile")
        try:
            page.wait_for_selector("a.item:has-text('机构入驻')", timeout=5000)
            print("[+] 等待5秒 cookie 失效")
            #失效直接删除json文件
            deleteFile(account_file,type,account_uid,account_third_id)
            context.close()
            browser.close()
            playwright.stop()
            return False
        except:
            print("[+] cookie 有效")
            context.close()
            browser.close()
            playwright.stop()
            return True

# 腾讯视频号cookie校验
def tencent_cookie_auth(account_file,type,account_uid,account_third_id):
    if not os.path.exists(account_file):
        return False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page = context.new_page()
        # 访问指定的 URL
        page.goto("https://channels.weixin.qq.com/platform/post/create")
        try:
            page.wait_for_selector('div.title-name:has-text("视频号小店")', timeout=5000)  # 等待5秒
            print("[+] 等待5秒 cookie 失效")
            #失效直接删除json文件
            deleteFile(account_file,type,account_uid,account_third_id)
            context.close()
            browser.close()
            playwright.stop()
            return False
        except:
            print("[+] cookie 有效")
            context.close()
            browser.close()
            playwright.stop()
            return True

# 小红书cookie校验
def xhs_cookie_auth(account_file,type,account_uid,account_third_id):
    if not os.path.exists(account_file):
        return False
    with open(account_file, 'r') as file:  
        # 读取文件内容  
        cookie = file.read()
    try:
        xhs_client = XhsClient(cookie, sign=sign)
        info_res = xhs_client.get_self_info()
        if not info_res:
           deleteFile(account_file,type,account_uid,account_third_id)
           return False
        else:
           return True
    except RequestException as err:
        print(f"Error: {err}")
        deleteFile(account_file,type,account_uid,account_third_id)
        return False
    except xhs_exception as err:
        print(f"Error: {err}")
        deleteFile(account_file,type,account_uid,account_third_id)
        return False
    except BaseException as err:
        print(f"Error: {err}")
        deleteFile(account_file,type,account_uid,account_third_id)
        return False


# 创建mysql连接 TODO 待优化
db_connector = pymysql.connect(
    host=MYSQL_CONF['host'],
    port=MYSQL_CONF['port'],
    user=MYSQL_CONF['username'],
    password=MYSQL_CONF['password'],
    database=MYSQL_CONF['database'],
    autocommit=MYSQL_CONF['auto_commit'],
)

def publishSuccess(mycursor,queue_id,status,task_queue_id):
     # 数据库更新为失败
     mycursor.execute(f"UPDATE mx_publish_task_video_queue SET status={status} WHERE id={queue_id}")
     # 父级的任务表增加一次失败次数fail_num+1
     mycursor.execute(f"UPDATE mx_publish_task_queue SET publish_num=publish_num+1 WHERE id={task_queue_id}")


def publishFail(mycursor,queue_id,status,task_queue_id):
     # 数据库更新为失败
     mycursor.execute(f"UPDATE mx_publish_task_video_queue SET status={status} WHERE id={queue_id}")
     # 父级的任务表增加一次失败次数fail_num+1
     mycursor.execute(f"UPDATE mx_publish_task_queue SET fail_num=fail_num+1 WHERE id={task_queue_id}")
#查询数据库处理
while True:
    try: 
        with db_connector.cursor() as mycursor: 
            # 执行查询语句  
            mycursor.execute("SELECT id,uid,type,account_info_id,title,tags,preview,path,url,location,publish_date,task_queue_id FROM mx_publish_task_video_queue WHERE status=0")  
            # 获取查询结果
            print("执行一次查询")
            for x in mycursor.fetchall():
                print(f"执行ID为{x[0]}的数据")
                queue_id = x[0]
                uid = x[1]
                type = x[2]
                account_info_id = x[3]
                video_title = x[4]
                video_description = ''
                video_tags = x[5]
                video_preview = x[6]
                video_path = x[7]
                location = x[9] if x[9] else "重庆市"
                publish_date = x[10]
                task_queue_id = x[11]
                # 更新数据
                mycursor.execute(f"UPDATE mx_publish_task_video_queue SET status=1 WHERE id={queue_id}") 
                # 查询第三方登录用户表
                mycursor.execute("SELECT id,uid,account_id FROM mx_account_info WHERE id="f"{account_info_id}") 
                account_info = mycursor.fetchone()
                account_uid = account_info[1]
                account_third_id = account_info[2]
                try:
                    if type == 1:
                        account_file = Path(BASE_DIR / "douyin_uploader"/"account"/ f"{account_uid}_{account_third_id}_account.json")
                        if douyin_cookie_auth(account_file,type,account_uid,account_third_id) == False:
                            # 登录失效将队列status改为4，相当于告诉用户重新登陆
                            publishFail(mycursor,queue_id,4,task_queue_id)
                            # 继续循环
                            continue
                    elif type == 2:
                        account_file = Path(BASE_DIR / "tencent_uploader"/"account"/ f"{account_uid}_{account_third_id}_account.json")
                        if tencent_cookie_auth(account_file,type,account_uid,account_third_id) == False:
                            # 登录失效将队列status改为4，相当于告诉用户重新登陆
                            publishFail(mycursor,queue_id,4,task_queue_id)
                            # 继续循环
                            continue
                    elif type == 3:
                        account_file = Path(BASE_DIR / "xhs_uploader"/"account"/ f"{account_uid}_{account_third_id}_account.json")
                        if xhs_cookie_auth(account_file,type,account_uid,account_third_id) == False:
                            # 登录失效将队列status改为4，相当于告诉用户重新登陆
                            publishFail(mycursor,queue_id,4,task_queue_id)
                            # 继续循环
                            continue
                    elif type == 4:
                        account_file = Path(BASE_DIR / "ks_uploader"/"account"/ f"{account_uid}_{account_third_id}_account.json")
                        if ks_cookie_auth(account_file,type,account_uid,account_third_id) == False:
                            # 登录失效将队列status改为4，相当于告诉用户重新登陆
                            publishFail(mycursor,queue_id,4,task_queue_id)
                            # 继续循环
                            continue
                    else:
                        # 类型不对直接改为失败
                        publishFail(mycursor,queue_id,3,task_queue_id)
                        continue
                except:
                    # cookie认证报错，将任务改为失败后跳过
                    publishFail(mycursor,queue_id,3,task_queue_id) 
                    print(f"Error: {err}") 
                    traceback.print_exc()
                    error_num+=1 
                    # 继续循环
                    continue
                if publish_date:
                    publish_datetimes = datetime.strptime(publish_date, "%Y-%m-%d %H:%M:%S")
                else:
                    publish_datetimes = 0
                if type == 1:
                    app = DouYinVideo(video_title,get_file_absolute_path(video_path), 
                    get_data_hashtags(video_tags),publish_datetimes,
                    account_file,location)
                    asyncio.run(app.main(), debug=False) 
                    # 没问题改为成功
                    publishSuccess(mycursor,queue_id,2,task_queue_id)  
                elif type == 2:
                    app = TencentVideo(video_title,get_file_absolute_path(video_path), 
                    get_data_hashtags(video_tags),publish_datetimes,
                    account_file,location)
                    asyncio.run(app.main(), debug=False) 
                    # 没问题改为成功
                    publishSuccess(mycursor,queue_id,2,task_queue_id)
                elif type == 3:
                    # 小红书需要有封面图
                    upload_res = upload_xhs_video(video_title,get_file_absolute_path(video_path),
                    get_data_hashtags(video_tags),publish_date,video_description,
                    get_file_absolute_path(video_preview),account_file)
                    if upload_res:
                        # 没问题改为成功
                        publishSuccess(mycursor,queue_id,2,task_queue_id)
                    else:
                        # 失败改数据库为失败
                        publishFail(mycursor,queue_id,3,task_queue_id)
                elif type == 4:
                    # 快手视频上传
                    app = KuaiShouVideo(video_title,get_file_absolute_path(video_path), 
                    get_data_hashtags(video_tags),publish_datetimes,
                    account_file,location)
                    asyncio.run(app.main(), debug=False) 
                    # 没问题改为成功
                    publishSuccess(mycursor,queue_id,2,task_queue_id)  
                else:
                    publishFail(mycursor,queue_id,3,task_queue_id) 
    except RequestException as err:
        # 更新为失败
        publishFail(mycursor,queue_id,3,task_queue_id)
        print(f"Error: {err}") 
        traceback.print_exc()
        error_num+=1
    except db_connector.Error as err:
        # 更新为失败
        publishFail(mycursor,queue_id,3,task_queue_id)  
        print(f"Error: {err}") 
        traceback.print_exc()
        error_num+=1
    except BaseException as err:
        # 更新为失败
        publishFail(mycursor,queue_id,3,task_queue_id)  
        error_num+=1
        print(f"Error: {err}")
        traceback.print_exc()
    except:
        # 任何其他异常更新为失败
        publishFail(mycursor,queue_id,3,task_queue_id)  
        error_num+=1
        traceback.print_exc()
    #错误超过10次则退出脚本
    if error_num > 10:
        break
    time.sleep(5)
db_connector.close()
