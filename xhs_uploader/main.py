import asyncio
import configparser
import qrcode
import base64  
import io  
import os
import pathlib
import requests
import time
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
        last_status = None
        while True:
            try:
                check_qrcode = xhs_client.check_qrcode(qr_id, qr_code)
            except Exception as exc:
                report(f"查询扫码状态失败：{type(exc).__name__}: {exc}", "WARN")
                check_qrcode = {}
            status = str(check_qrcode.get("code_status") or "")
            # 状态只在变化时提示，避免刷屏
            if status != last_status:
                last_status = status
                if status == "1":
                    report("已扫码，请在手机小红书 App 上点「确认登录」")
                elif status == "3":
                    LAST_LOGIN_ERROR = "二维码已被取消或失效，请重新点击「去登录」"
                    report(LAST_LOGIN_ERROR, "ERROR")
                    try:
                        qrcode_path.unlink()
                    except Exception:
                        pass
                    return False
            if status == "2":
                report("已扫码，正在获取小红书账号信息…")
                # cookie 可能还没同步给本客户端，取账号信息要重试几次，
                # 否则 third_id 为空会写成「{id}__account.json」并导致账号表空着
                user_info_res = {}
                third_id = ""
                for _ in range(3):
                    try:
                        user_info_res = XhsClient(xhs_client.cookie, sign=_sign).get_self_info2()
                    except Exception as exc:
                        report(f"读取账号信息失败，重试中：{type(exc).__name__}: {exc}", "WARN")
                        user_info_res = {}
                    third_id = str(user_info_res.get('user_id') or '')
                    if third_id:
                        break
                    sleep(1)
                if not third_id:
                    LAST_LOGIN_ERROR = "扫码成功，但读取账号信息失败（接口未返回 user_id），请重新扫码"
                    report(LAST_LOGIN_ERROR, "ERROR")
                    try:
                        qrcode_path.unlink()
                    except Exception:
                        pass
                    return False
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
            if num == 100:
                report("二维码还剩约 20 秒有效期，请尽快扫码并在 App 内确认登录", "WARN")
            if num > 120:
                LAST_LOGIN_ERROR = (
                    "二维码已超时，没有检测到扫码确认"
                    if not last_status or last_status == "0"
                    else "已扫码但没有在有效期内确认登录，请重新点击「去登录」并尽快在手机上点「确认」"
                )
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

# ---------------------------------------------------------------- 浏览器发布
# 小红书创作者接口要求人机验证（Verifytype 124），API 方式频繁被拦；
# 这里改走网页自动化，和其它平台一致：上传文件 → 填标题正文 → 点发布。

XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
TITLE_LIMIT = 20
BODY_LIMIT = 1000

# 「发布」按钮藏在自定义组件 xhs-publish-btn 的 closed shadow DOM 里，定位器进不去。
# 页面加载前 hook 住 attachShadow 把 shadow root 存下来，就能拿到按钮真实位置；
# 外部监听器看到的 target 会被重定向成宿主，但事件本身是能到内部按钮的。
SHADOW_HOOK_JS = """
(() => {
  if (window.__xhsShadowRoots) return;
  window.__xhsShadowRoots = [];
  const orig = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = orig.call(this, init);
    try { window.__xhsShadowRoots.push(root); } catch (e) {}
    return root;
  };
})();
"""

# 点发布后平台冒出来的拦截提示（账号层面，自动化绕不过去）
BLOCK_HINTS = {
    "未绑定手机号": "小红书账号未绑定手机号，平台不允许发布笔记。请在手机 App「设置 - 账号与安全」绑定手机号后重试",
    "绑定手机号后才可发布": "小红书账号未绑定手机号，平台不允许发布笔记。请先在手机 App 里绑定手机号",
    "完成验证": "小红书要求人机验证（网页版无法自动通过），请先用浏览器手动发一次或完成验证",
    "拖动滑块": "小红书弹出滑块验证，请先手动完成一次验证再重试",
    "请完成安全验证": "小红书弹出安全验证，请先手动完成一次验证再重试",
    "涉嫌违规": "小红书判定内容涉嫌违规，已中止发布",
    "发布失败": "小红书提示发布失败，请到创作服务平台查看原因",
    "上传失败": "小红书视频上传失败（可能网络或格式问题）",
}


def _cookie_list(raw: str, domain: str = ".xiaohongshu.com") -> list[dict]:
    """账号文件存的是 `a=b; c=d` 形式的 cookie 串，转成 Playwright 的 cookies。"""
    items = []
    for chunk in raw.replace("\n", ";").split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        items.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return items


async def _wait_form_ready(page, timeout: float = 300) -> bool:
    """等标题框出现，说明视频已经进了发布表单。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if await page.locator('input[placeholder*="填写标题"]').count():
                return True
        except Exception:
            pass
        await asyncio.sleep(2)
    return False


async def _fill_title(page, title: str) -> None:
    box = page.locator('input[placeholder*="填写标题"]').first
    await box.wait_for(state="visible", timeout=30000)
    await box.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.insert_text(title[:TITLE_LIMIT])


async def _fill_body(page, text: str, tags: list[str]) -> None:
    editor = page.locator("div.tiptap").first
    await editor.wait_for(state="visible", timeout=30000)
    await editor.click()
    await asyncio.sleep(0.5)

    content = (text or "").strip()[:BODY_LIMIT]
    if content:
        await page.keyboard.insert_text(content)
        await page.keyboard.press("Enter")

    for tag in tags:
        tag = (tag or "").strip().lstrip("#")
        if not tag:
            continue
        # 输入 # 会弹话题联想，先关掉，保留纯文本话题（发布后仍会被识别为话题）
        await page.keyboard.type(f"#{tag}", delay=40)
        await asyncio.sleep(0.6)
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.2)
        await page.keyboard.type(" ", delay=30)


BTN_STATE_JS = """() => {
    const roots = window.__xhsShadowRoots || [];
    for (const r of roots) {
        const btn = r.querySelector('button.ce-btn.bg-red');
        if (!btn) continue;
        const b = btn.getBoundingClientRect();
        return {
            found: true,
            disabled: btn.disabled,
            rect: [b.x, b.y, b.width, b.height],
        };
    }
    return {found: false};
}"""


async def _click_publish(page) -> bool:
    """点「发布」。

    按钮在 xhs-publish-btn 的 closed shadow DOM 里：locator.click 只能打到宿主，
    内部按钮收不到；外部监听到的 target 也会被重定向成宿主。
    这里用 hook 拿到的 shadow root 查按钮真实坐标，再用真实鼠标点击。
    """
    await page.locator("xhs-publish-btn").first.wait_for(state="visible", timeout=30000)

    state = {}
    for _ in range(30):
        state = await page.evaluate(BTN_STATE_JS)
        if state.get("found") and not state.get("disabled"):
            break
        await asyncio.sleep(1)

    if not state.get("found"):
        return False
    x, y, w, h = state["rect"]
    if w <= 0 or h <= 0:
        return False

    cx, cy = x + w / 2, y + h / 2
    await page.mouse.move(cx, cy)
    await page.wait_for_timeout(250)
    await page.mouse.down()
    await page.wait_for_timeout(90)
    await page.mouse.up()
    return True


async def _read_page_text(page) -> str:
    try:
        return await page.evaluate("() => (document.body && document.body.innerText) || ''")
    except Exception:
        return ""


async def _wait_publish_result(page, timeout: float = 150) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = page.url
        except Exception:
            url = ""
        text = await _read_page_text(page)

        if "发布成功" in text:
            return True
        if "/publish/success" in url or "note-manager" in url:
            return True

        for hint, message in BLOCK_HINTS.items():
            if hint in text:
                raise RuntimeError(message)

        await asyncio.sleep(2)
    return False


async def _publish_by_browser(title, video_path, topics, description, account_file, dry_run=False) -> bool:
    from playwright.async_api import async_playwright
    from utils.browser_mode import (
        CHROME_ARGS, STEALTH_JS, context_kwargs,
        find_chrome_executable, headless_enabled,
    )

    raw = open(account_file, "r", encoding="utf-8").read()
    cookies = _cookie_list(raw)
    if not cookies:
        report("小红书账号文件里没有可用的 cookie，请重新登录", "ERROR")
        return False

    headless = headless_enabled()
    chrome = find_chrome_executable()
    report(f"小红书：使用系统 Chrome{'（无头）' if headless else '（有头）'}" if chrome
           else "小红书：未检测到 Chrome，使用内置 Chromium（可能上传失败）", "INFO")

    launch_kwargs = {"headless": headless}
    if chrome:
        launch_kwargs["executable_path"] = chrome
    launch_kwargs["args"] = [*CHROME_ARGS, "--start-maximized"] if not headless else CHROME_ARGS

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        try:
            ctx_kwargs = context_kwargs(browser, headless)
            context = await browser.new_context(**ctx_kwargs)
            await context.add_init_script(STEALTH_JS)
            # 必须在页面脚本执行前装 hook，否则拿不到 closed shadow root
            await context.add_init_script(SHADOW_HOOK_JS)
            await context.add_cookies(cookies)
            page = await context.new_page()

            report("小红书：打开发布页…", "INFO")
            await page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            if "login" in page.url or "passport" in page.url:
                raise RuntimeError("登录已失效，请在账号页重新扫码登录小红书")

            page_text = await _read_page_text(page)
            skip_precheck = os.environ.get("MATRIX_XHS_SKIP_PRECHECK") == "1"
            if not skip_precheck and ("后才可发布笔记" in page_text or "未绑定手机号" in page_text):
                raise RuntimeError(BLOCK_HINTS["未绑定手机号"])

            upload = page.locator("input.upload-input").first
            await upload.wait_for(state="attached", timeout=60000)
            await upload.set_input_files(video_path)
            report("小红书：视频已提交上传，等待表单…", "INFO")

            if not await _wait_form_ready(page):
                raise RuntimeError("小红书发布表单没有加载出来（可能视频转码失败或登录态异常）")

            await _fill_title(page, title)
            await _fill_body(page, description or title, topics)
            await page.wait_for_timeout(1500)

            # 正文没填进去会导致发布被拒，先自查一次
            try:
                written = await page.locator("div.tiptap").first.inner_text()
            except Exception:
                written = ""
            if not (written or "").strip():
                raise RuntimeError("小红书正文没有写进去，已中止发布")

            if dry_run:
                report("小红书：已填写完成（干跑，不点发布）", "INFO")
                return True

            report("小红书：点击发布…", "INFO")
            if not await _click_publish(page):
                raise RuntimeError("找不到小红书发布按钮")

            # 拦截类提示（如「未绑定手机号」）只显示几秒，抢在前面读一次
            await page.wait_for_timeout(2000)
            toast = await _read_page_text(page)
            for hint, message in BLOCK_HINTS.items():
                if hint in toast:
                    raise RuntimeError(message)

            if not await _wait_publish_result(page):
                raise RuntimeError("点了发布但没有等到成功结果，请到创作服务平台确认")
            report("小红书：发布成功", "INFO")
            return True
        finally:
            await browser.close()


def upload_xhs_video(title, video_path, topics, publish_datetimes, description, cover_path, account_file):
    """发布入口：默认走浏览器自动化；MATRIX_XHS_MODE=api 可回退旧的接口方式。"""
    mode = (os.environ.get("MATRIX_XHS_MODE") or "browser").strip().lower()
    dry_run = os.environ.get("MATRIX_DRY_RUN") == "1"

    if mode == "api":
        return _upload_by_api(title, video_path, topics, publish_datetimes,
                              description, cover_path, account_file)

    if publish_datetimes:
        report("小红书：暂不支持网页版定时发布，本次按立即发布处理", "WARN")

    try:
        return asyncio.run(_publish_by_browser(
            title, video_path, topics or [], description, account_file, dry_run,
        ))
    except Exception as err:
        print(f"Error: {err}")
        print(traceback.format_exc())
        report_exc("小红书发布失败", err)
        return False


def _upload_by_api(title, video_path, topics, publish_datetimes, description, cover_path, account_file):
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
