import configparser
import qrcode
import base64  
import io  
import os
import pathlib
import requests
import redis
import traceback
from PIL import Image
from playwright.sync_api import sync_playwright
from time import sleep
from conf import BASE_DIR,REDIS_CONF, XHS_SERVER
from xhs import XhsClient
from requests import RequestException

config = configparser.RawConfigParser()
config.read('accounts.ini')


def sign_local(uri, data=None, a1="", web_session=""):
    for _ in range(10):
        try:
            with sync_playwright() as playwright:
                stealth_js_path = pathlib.Path(
                    BASE_DIR) / "xhs_uploader" / "cdn.jsdelivr.net_gh_requireCool_stealth.min.js_stealth.min.js"
                chromium = playwright.chromium

                # 如果一直失败可尝试设置成 False 让其打开浏览器，适当添加 sleep 可查看浏览器状态
                browser = chromium.launch(headless=True)

                browser_context = browser.new_context()
                browser_context.add_init_script(path=stealth_js_path)
                context_page = browser_context.new_page()
                context_page.goto("https://www.xiaohongshu.com")
                browser_context.add_cookies([
                    {'name': 'a1', 'value': a1, 'domain': ".xiaohongshu.com", 'path': "/"}]
                )
                context_page.reload()
                # 这个地方设置完浏览器 cookie 之后，如果这儿不 sleep 一下签名获取就失败了，如果经常失败请设置长一点试试
                sleep(2)
                encrypt_params = context_page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
                return {
                    "x-s": encrypt_params["X-s"],
                    "x-t": str(encrypt_params["X-t"])
                }
        except Exception:
            # 这儿有时会出现 window._webmsxyw is not a function 或未知跳转错误，因此加一个失败重试趴
            pass
    raise Exception("重试了这么多次还是无法签名成功，寄寄寄")


def sign(uri, data=None, a1="", web_session=""):
    # 填写自己的 flask 签名服务端口地址
    res = requests.post(f"{XHS_SERVER}/sign",
                        json={"uri": uri, "data": data, "a1": a1, "web_session": web_session})
    signs = res.json()
    return {
        "x-s": signs["x-s"],
        "x-t": signs["x-t"]
    }
def cache_data(key:str,value:str,timeout=60)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.set(key, value)
    redis_client.expire(key, timeout)

def xhs_setup(account_file_path, handle=False ,account_id="",queue_id=""):
    try:
        xhs_client = XhsClient(sign=sign)
        qr_res = xhs_client.get_qrcode()
        qr_id = qr_res["qr_id"]
        qr_code = qr_res["code"]
        qr_res["url"]
        qr = qrcode.QRCode(version=1, error_correction=qrcode.ERROR_CORRECT_L,
                        box_size=50,
                        border=1)
        qr.add_data(qr_res["url"])
        qr.make()
        img = qr.make_image(fill_color="black", back_color="white")
        qrcode_path = pathlib.Path(
                        BASE_DIR) / "xhs_uploader" / "qrcode"/f"qrcode_{queue_id}.png"
        img.save(qrcode_path)
        # 获取二维码图像的字节流
        # 打开图片文件 
        image = Image.open(qrcode_path)  
        # 将图片转换为字节对象  
        img_bytes = io.BytesIO()  
        image.save(img_bytes, format='PNG')
        img_bytes.seek(0)   
        base64_data = "data:image/png;base64,"+base64.b64encode(img_bytes.read()).decode()
        # 将id和登录url的关系存到redis
        cache_data(f"xhs_login_ewm_{queue_id}",base64_data)
        # 记录二维码完成后删除二维码文件
        if os.path.exists(qrcode_path):
            os.remove(qrcode_path)
        user_info = False
        num=1
        while True:
            check_qrcode = xhs_client.check_qrcode(qr_id,qr_code)
            sleep(1)
            if check_qrcode["code_status"] == 2:
                # 按照当前登录用户，获取用户信息
                xhs_res_client = XhsClient(xhs_client.cookie, sign=sign)
                user_info_res = xhs_res_client.get_self_info2()
                third_id = user_info_res['user_id']
                user_info = {
                    'account_id':third_id,
                    'username':user_info_res['nickname'],
                    'avatar':user_info_res['images'],
                }
                # 保存抖音账号的登录状态，时间一个周
                account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
                file = open(account_file, 'a')
                # 写入数据到文件中
                file.write(xhs_client.cookie)
                # 关闭文件
                file.close()
                # 记录登录状态 记录当前用户的登陆状态，只算此次
                cache_data(f"xhs_login_status_{account_id}",1,60)
                # 记录xhs的ID的登录状态，算作一天过期，目前未知
                cache_data(f"xhs_login_status_third_{account_id}_{third_id}",1,86400)
                return user_info
            # 如果查询100次还未登录，直接返回登陆失败
            num+=1
            if num > 100:
                return user_info
    except:
        return False

def upload_xhs_video(title,video_path,topics,publish_datetimes,description,cover_path,account_file):
    with open(account_file, 'r') as file:  
        # 读取文件内容  
        cookie = file.read()
    try:
        xhs_client = XhsClient(cookie, sign=sign)
        if not description:
            description = title
        if not publish_datetimes:
            publish_datetimes = None
        video_pub_info = xhs_client.create_video_note(
            title=title,
            desc=description,
            topics=topics,
            post_time=publish_datetimes,
            video_path=video_path,
            cover_path=cover_path
        )
        print(video_pub_info)
        return True
    except RequestException as err:
        print(f"Error: {err}")
        print(traceback.format_exc())
        return False
    except BaseException as err:
        print(f"Error: {err}")
        print(traceback.format_exc())
        return False
    return True
