import configparser
import qrcode
import base64  
import io  
import os
import pathlib
import requests
import traceback
from PIL import Image
from playwright.sync_api import sync_playwright
from time import sleep
from conf import BASE_DIR, XHS_SERVER
from utils.cache_store import cache_data
from utils.login_diag import publish_qrcode, report, report_exc
from xhs import XhsClient
from requests import RequestException

# 最近一次登录失败原因，桌面端会读取展示
LAST_LOGIN_ERROR = ""

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
                browser = chromium.launch(headless=True, channel="chromium")

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


# 允许外部注入签名实现（桌面客户端使用进程内签名，不再依赖 Flask 服务）
SIGN_FUNC = None


def _sign(uri, data=None, a1="", web_session=""):
    if SIGN_FUNC is not None:
        return SIGN_FUNC(uri, data, a1, web_session)
    return sign(uri, data, a1, web_session)


def _qrcode_dir():
    """二维码临时目录：优先放数据目录，避免安装到只读路径时写不进去。"""
    try:
        from desktop.core import paths

        directory = paths.data_root() / "qrcode"
    except Exception:
        directory = pathlib.Path(BASE_DIR) / "xhs_uploader" / "qrcode"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def xhs_setup(account_file_path, handle=False ,account_id="",queue_id=""):
    global LAST_LOGIN_ERROR
    LAST_LOGIN_ERROR = ""
    try:
        xhs_client = XhsClient(sign=_sign)
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
        qrcode_path = _qrcode_dir() / f"xhs_qrcode_{queue_id}.png"
        img.save(qrcode_path)
        image = Image.open(qrcode_path)
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        base64_data = "data:image/png;base64,"+base64.b64encode(img_bytes.read()).decode()
        cache_data(f"xhs_login_ewm_{queue_id}",base64_data)

        # 小红书没有浏览器窗口，二维码必须弹给用户看
        publish_qrcode(qrcode_path)
        report("小红书二维码已生成，请用小红书 App 扫码（有效期约 2 分钟）")

        num = 1
        while True:
            try:
                check_qrcode = xhs_client.check_qrcode(qr_id, qr_code)
            except Exception as exc:
                report(f"查询扫码状态失败：{type(exc).__name__}: {exc}", "WARN")
                check_qrcode = {}
            if str(check_qrcode.get("code_status")) == "2":
                report("已扫码，正在获取小红书账号信息…")
                xhs_res_client = XhsClient(xhs_client.cookie, sign=_sign)
                user_info_res = xhs_res_client.get_self_info2()
                third_id = str(user_info_res.get('user_id') or '')
                user_info = {
                    'account_id': third_id,
                    'username': user_info_res.get('nickname') or third_id,
                    'avatar': user_info_res.get('images') or '',
                }
                account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
                with open(account_file, 'w', encoding='utf-8') as file:
                    file.write(xhs_client.cookie)
                cache_data(f"xhs_login_status_{account_id}",1,60)
                cache_data(f"xhs_login_status_third_{account_id}_{third_id}",1,86400)
                try:
                    qrcode_path.unlink()
                except Exception:
                    pass
                report(f"小红书账号已保存：{user_info['username']}（{third_id}）")
                return user_info
            sleep(1)
            num += 1
            if num > 120:
                LAST_LOGIN_ERROR = "二维码已超时，没有检测到扫码（请重新点击「去登录」）"
                report(LAST_LOGIN_ERROR, "ERROR")
                try:
                    qrcode_path.unlink()
                except Exception:
                    pass
                return False
    except Exception as exc:
        LAST_LOGIN_ERROR = f"{type(exc).__name__}: {exc}"
        report_exc("小红书登录失败", exc)
        return False

def upload_xhs_video(title,video_path,topics,publish_datetimes,description,cover_path,account_file):
    with open(account_file, 'r') as file:  
        # 读取文件内容  
        cookie = file.read()
    try:
        xhs_client = XhsClient(cookie, sign=_sign)
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
        report_exc("小红书发布失败（网络/风控）", err)
        return False
    except BaseException as err:
        print(f"Error: {err}")
        print(traceback.format_exc())
        report_exc("小红书发布失败", err)
        return False
    return True
