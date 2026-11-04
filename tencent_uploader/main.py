# -*- coding: utf-8 -*-
from datetime import datetime
from playwright.async_api import Playwright, async_playwright
import os
import re
import time
import asyncio
import subprocess
import sys

from utils.files_times import get_absolute_path
from utils.cache_store import cache_data
from utils.browser_login import LoginAborted, pick_id_by_cookies, wait_for_login
from utils.browser_mode import headless_enabled
from utils.login_diag import report, report_exc

LOGIN_TIMEOUT = 300
# 最近一次登录失败原因，桌面端会读取展示
LAST_LOGIN_ERROR = ""

WEIXIN_LOGIN_URL = "https://channels.weixin.qq.com/platform/login-for-iframe?dark_mode=true&host_type=1"
WEIXIN_PLATFORM_URL = "https://channels.weixin.qq.com/platform"


def _find_chrome() -> str:
    """视频号上传依赖系统 Chrome（h264 编码支持），找不到就回退内置 Chromium。

    返回 Chrome 可执行文件路径；空串表示没有可用 Chrome。
    用路径而不是 channel 名启动：部分 Playwright 版本识别不到新版 Chrome 的注册信息，
    channel="chrome" 会直接报 "Chromium distribution 'chrome' is not found"。
    """
    override = (os.environ.get("MATRIX_TENCENT_CHANNEL") or "").strip()
    if override:
        if override.lower() in ("none", "off", "0"):
            return ""
        if os.path.exists(override):
            return override
        # 形如 "chrome" 之类的别名，继续走下面的自动探测
    if sys.platform.startswith("win"):
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                         r"Google\Chrome\Application\chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                         r"Google\Chrome\Application\chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA",
                                        os.path.expanduser(r"~\AppData\Local")),
                         r"Google\Chrome\Application\chrome.exe"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return ""
    try:
        out = subprocess.run(
            ["which", "google-chrome"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=3, check=True,
        ).stdout.decode().strip()
        return out if out and os.path.exists(out) else ""
    except Exception:
        return ""



def format_str_for_short_title(origin_title: str) -> str:
    # 定义允许的特殊字符
    allowed_special_chars = "《》“”:+?%°"

    # 移除不允许的特殊字符
    filtered_chars = [char if char.isalnum() or char in allowed_special_chars else ' ' if char == ',' else '' for
                      char in origin_title]
    formatted_string = ''.join(filtered_chars)

    # 调整字符串长度
    if len(formatted_string) > 16:
        # 截断字符串
        formatted_string = formatted_string[:16]
    elif len(formatted_string) < 6:
        # 使用空格来填充字符串
        formatted_string += ' ' * (6 - len(formatted_string))

    return formatted_string


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel="chromium")
        context = await browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://channels.weixin.qq.com/platform/post/create")
        try:
            await page.wait_for_selector('div.title-name:has-text("视频号小店")', timeout=5000)  # 等待5秒
            print("[+] 等待5秒 cookie 失效")
            return False
        except:
            print("[+] cookie 有效")
            return True

async def _weixin_logged_in(page) -> bool:
    """快速判断：只有页面自己已经跳到 /platform 才算登录成功。"""
    try:
        url = page.url
    except Exception:
        return False
    if "login" in url:
        return False
    return WEIXIN_PLATFORM_URL in url


async def _weixin_probe(page) -> bool:
    """另开一页访问视频号后台，被弹回 login.html 就说明还没登录。

    ``login-for-iframe`` 是给 iframe 内嵌用的登录页，扫码成功后它**自己不会跳转**，
    只向父窗口发消息。所以既不能等 URL 变化，也不能等页面元素——原实现用
    ``div.qrcode`` 之类的选择器，改版后直接失效，用户扫完码界面仍显示"未登录"。
    这里改成用同一个 context 里的 cookie 另开一页实测，最可靠。
    """
    context = page.context
    try:
        probe = await context.new_page()
    except Exception as exc:  # 浏览器已被关闭
        raise LoginAborted("登录窗口被关闭了，请重新点击「去登录」") from exc
    try:
        await probe.goto(WEIXIN_PLATFORM_URL, timeout=20000, wait_until="domcontentloaded")
        await probe.wait_for_timeout(2000)
        return await _weixin_logged_in(probe)
    except Exception:
        return False
    finally:
        try:
            await probe.close()
        except Exception:
            pass
        # 把焦点还给扫码页，别让用户对着探测页发愣
        try:
            await page.bring_to_front()
        except Exception:
            pass


def _build_weixin_check():
    """给 wait_for_login 用的检测回调。

    登录页在扫码前整个域一个 cookie 都没有，所以「出现 cookie」≈ 已经扫码；
    出现 cookie 后每 4 秒实测一次后台，没 cookie 时放宽到 30 秒，
    避免对着一个还没人扫的页面反复开标签页。
    """
    state = {"next": 0.0, "notified": False}

    async def check(page) -> bool:
        if await _weixin_logged_in(page):
            return True
        try:
            cookies = await page.context.cookies()
        except Exception:
            return False
        if cookies and not state["notified"]:
            state["notified"] = True
            report("已扫码，请在手机上点「确认登录」")
        now = time.time()
        if now < state["next"]:
            return False
        state["next"] = now + (4.0 if cookies else 30.0)
        return await _weixin_probe(page)

    return check


async def _read_weixin_identity(page, cookies) -> dict:
    """读取视频号 ID / 昵称 / 头像；读不到就留空，不影响发布。"""
    third_id = ""
    username = ""
    avatar = ""

    try:
        # 注意：登录页 URL 是 /platform/login-for-iframe，同样包含 /platform，
        # 不能只看 "/platform in url" 判断是否已在控制台，否则永远不会跳转。
        if "login" in page.url or WEIXIN_PLATFORM_URL not in page.url:
            await page.goto(WEIXIN_PLATFORM_URL, timeout=30000)
        # 控制台是重 SPA，首屏 3 秒往往渲染不完，等具体元素出现再读
        try:
            await page.wait_for_selector(
                "h2.finder-nickname, span.finder-uniq-id, img.avatar", timeout=15000
            )
        except Exception:
            pass
        await page.wait_for_timeout(800)
    except Exception:
        pass

    for selector in ("span.finder-uniq-id", "span[class*='uniq-id']"):
        try:
            locator = page.locator(selector).first
            if await locator.count() and await locator.is_visible():
                third_id = (await locator.inner_text()).strip()
                if third_id:
                    break
        except Exception:
            continue

    if not third_id:
        try:
            text = await page.evaluate("() => (document.body && document.body.innerText) || ''")
            match = re.search(r"(?:视频号|微信号)[:：]\s*([A-Za-z0-9_.\-]{3,})", text or "")
            if match:
                third_id = match.group(1)
        except Exception:
            pass

    for selector in ("h2.finder-nickname", "h2[class*='nickname']", "span[class*='nickname']"):
        try:
            locator = page.locator(selector).first
            if await locator.count() and await locator.is_visible():
                text = (await locator.inner_text()).strip()
                if text and len(text) <= 40:
                    username = text
                    break
        except Exception:
            continue

    if not avatar:
        try:
            locator = page.locator("img.avatar").first
            if await locator.count():
                avatar = await locator.get_attribute("src") or ""
        except Exception:
            pass

    # 页面结构会变，再兜一层：从 localStorage / 页面文本里捞昵称和视频号 ID
    if not third_id or not username:
        try:
            bag = await page.evaluate(
                """() => {
                    const out = {};
                    try {
                        for (const k of Object.keys(localStorage)) {
                            out[k] = localStorage.getItem(k) || '';
                        }
                    } catch (e) {}
                    return out;
                }"""
            )
        except Exception:
            bag = {}
        joined = "\n".join(f"{k}={v}" for k, v in (bag or {}).items())
        if not username:
            match = re.search(r'"(?:nickname|nickName)"\s*:\s*"([^"]{1,40})"', joined)
            if match:
                username = match.group(1)
        if not third_id:
            match = re.search(r'"(?:uniqId|uniq_id|finderId)"\s*:\s*"([A-Za-z0-9_.\-]{3,})"', joined)
            if match:
                third_id = match.group(1)

    if not third_id:
        third_id = pick_id_by_cookies(cookies, ("wxuin", "bizuin"))

    return {"account_id": third_id, "username": username, "avatar": avatar}


async def save_storage_state(account_file_path: str,account_id:str,queue_id:str):
    global LAST_LOGIN_ERROR
    LAST_LOGIN_ERROR = ""
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            # 登录页会自己跳到 channels.weixin.qq.com/login.html，二维码在 iframe 里
            await page.goto(WEIXIN_LOGIN_URL, timeout=30000)
            report("视频号登录页已打开，请用微信扫码登录")

            ok = await wait_for_login(
                context, page,
                success_check=_build_weixin_check(),
                timeout=LOGIN_TIMEOUT,
            )
            if not ok:
                LAST_LOGIN_ERROR = f"等待扫码超时（{LOGIN_TIMEOUT} 秒），没有检测到登录状态"
                report(LAST_LOGIN_ERROR, "ERROR")
                return False

            report("已检测到视频号登录成功，正在保存登录信息…")
            cache_data(f"tencent_login_scan_{queue_id}", 1, 6)

            cookies = await context.cookies()
            user_info = await _read_weixin_identity(page, cookies)

            third_id = user_info.get("account_id") or ""
            if not third_id:
                third_id = f"wx{int(time.time())}"
                user_info["account_id"] = third_id
                report("未能读取到视频号 ID，已用临时 ID 代替（不影响发布）", "WARN")
            if not user_info.get("username"):
                user_info["username"] = third_id

            account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
            await context.storage_state(path=account_file)
            cache_data(f"tencent_login_status_{account_id}", 1, 60)
            cache_data(f"tencent_login_status_third_{account_id}_{third_id}", 1, 86400)

            await context.close()
            await browser.close()
            report(f"视频号账号已保存：{user_info['username']}（{third_id}）")
            return user_info
    except LoginAborted as exc:
        LAST_LOGIN_ERROR = str(exc)
        report(LAST_LOGIN_ERROR, "WARN")
        return False
    except Exception as exc:
        LAST_LOGIN_ERROR = f"{type(exc).__name__}: {exc}"
        report_exc("视频号登录失败", exc)
        return False


async def weixin_setup(account_file_path, handle=False ,account_id="",queue_id=""):
    user_info = await save_storage_state(account_file_path,account_id,queue_id)
    return user_info


class TencentVideo(object):
    def __init__(self, title, file_path,video_preview,tags, publish_date, account_file,location="重庆市",is_original=False,category="知识"):
        self.title = title  # 视频标题
        self.file_path = file_path # 视频文件路径
        self.video_preview = video_preview # 视频预览图路径
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.is_original = is_original
        self.category = category
        self.location = location
        self.local_executable_path = ""  # change me necessary！

    async def set_schedule_time_tencent(self, page, publish_date):
        print("click schedule")

        label_element = page.locator("label").filter(has_text="定时").nth(1)
        await label_element.click()

        await page.click('input[placeholder="请选择发表时间"]')

        publish_month = str(publish_date.month)
        
        if len(publish_month)<2:
            publish_month = f"0{publish_month}"

        current_month = f"{publish_month}月"

        # 获取当前的月份
        page_month = await page.inner_text('span.weui-desktop-picker__panel__label:has-text("月")')

        # 检查当前月份是否与目标月份相同
        if page_month != current_month:
            await page.click('button.weui-desktop-btn__icon__right')

        # 获取页面元素
        elements = await page.query_selector_all('table.weui-desktop-picker__table a')

        # 遍历元素并点击匹配的元素
        for element in elements:
            if 'weui-desktop-picker__disabled' in await element.evaluate('el => el.className'):
                continue
            text = await element.inner_text()
            if text.strip() == str(publish_date.day):
                await element.click()
                break

        # 输入小时部分（假设选择11小时）
        await page.click('input[placeholder="请选择时间"]')
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date.hour))

        # 选择标题栏（令定时时间生效）
        await page.locator("div.input-editor").click()

    async def handle_upload_error(self, page):
        print("视频出错了，重新上传中")
        await page.locator('div.media-status-content div.tag-inner:has-text("删除")').click()
        await page.get_by_role('button', name="删除", exact=True).click()
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        # 视频号对 h264 编码有要求，优先使用系统 Chrome；未安装时回退内置 Chromium
        launch_kwargs = {"headless": headless_enabled()}
        chrome_path = _find_chrome()
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path
            print(f"  [-] 使用系统 Chrome：{chrome_path}")
        else:
            print("  [!] 未检测到系统 Chrome，回退内置 Chromium（若视频转码失败请安装 Chrome）")
        browser = await playwright.chromium.launch(**launch_kwargs)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context_kwargs = {"storage_state": f"{self.account_file}"}
        if launch_kwargs["headless"]:
            # 无头模式 UA 带 HeadlessChrome，视频号会把 /post/create 重定向回首页，
            # 表单因此永远不出现；伪装成同版本正常 Chrome 即可。
            version = (browser.version or "140.0.0.0").strip()
            context_kwargs["user_agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{version} Safari/537.36"
            )
        context = await browser.new_context(**context_kwargs)
        
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://channels.weixin.qq.com/platform/post/create")
        print('[+]正在上传-------{}'.format(self.file_path))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        try:
            await page.wait_for_url("https://channels.weixin.qq.com/platform/post/create", timeout=20000)
        except Exception:
            if "login" in page.url:
                raise RuntimeError("视频号登录已失效，请到账号页重新扫码登录")
            raise
        if "login" in page.url:
            raise RuntimeError("视频号登录已失效，请到账号页重新扫码登录")
        # 直接给文件输入框塞文件：「点击上传」区域的 class 和文案会变，输入框相对稳定
        file_input = page.locator('input[type="file"]').first
        try:
            await file_input.wait_for(state="attached", timeout=30000)
            await file_input.set_input_files(self.file_path)
        except Exception as exc:
            print(f"  [!] 文件输入框不可用，改用点击上传区域：{type(exc).__name__}")
            upload_div_loc = page.locator("div.upload-content").first
            async with page.expect_file_chooser() as fc_info:
                await upload_div_loc.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.file_path)
        # 填充标题和话题
        await self.add_title_tags(page)
        # 添加位置
        # await self.add_location(page)
        # 取消合集功能
        # await self.add_collection(page)
        # 原创选择
        if self.is_original:
            await self.add_original(page)
        # 检测上传状态
        await self.detact_upload_status(page)
        # 是否定时，如果定时，时间由publish_date控制
        if self.publish_date != 0:
            await self.set_schedule_time_tencent(page, self.publish_date)
        # 添加短标题
        await self.add_short_title(page)

        await self.click_publish(page)

        await context.storage_state(path=f"{self.account_file}")  # 保存cookie
        print('  [-]cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()
        await playwright.stop()

    async def add_short_title(self, page):
        short_title_element = page.get_by_text("短标题", exact=True).locator("..").locator(
            "xpath=following-sibling::div").locator(
            'span input[type="text"]')
        if await short_title_element.count():
            short_title = format_str_for_short_title(self.title)
            await short_title_element.fill(short_title)

    async def click_publish(self, page):
        publish_button = page.locator('div.form-btns button:has-text("发表")')
        if not await publish_button.count():
            publish_button = page.get_by_role("button", name="发表", exact=True)
        if not await publish_button.count():
            raise RuntimeError("未找到「发表」按钮，发布页结构可能已变化")
        if os.environ.get("MATRIX_DRY_RUN") == "1":
            print("  [!] 干跑模式：已就绪到发表按钮，不实际点击")
            return
        await publish_button.first.click()
        print("  [-] 已点击发表，等待结果...")

        deadline = time.time() + 300
        while time.time() < deadline:
            if "/platform/post/list" in page.url:
                print("  [-]视频发布成功")
                return
            await asyncio.sleep(2)
        # 不当作失败：可能已经发出去了，重试会造成重复作品
        report("发表后 5 分钟没有跳到作品列表，请到后台确认是否已发布", "WARN")

    async def detact_upload_status(self, page):
        """等上传完成：发表按钮不再禁用即视为传完。

        旧实现是 while True，一旦「更换封面」或「发表」按钮不存在就永远卡在
        except 里，界面上只会看到一直"正在上传"，发布永远不会发生。
        """
        deadline = time.time() + 900
        started = time.time()
        while time.time() < deadline:
            try:
                button = page.get_by_role("button", name="发表")
                if not await button.count():
                    # 表单没渲染出来时不能无限空转：多半是浏览器不支持 h264 或页面结构变了
                    if time.time() - started > 90 and not await page.locator(
                            "div.input-editor, div[contenteditable='true']").count():
                        raise RuntimeError(
                            "视频号发布页没有加载出表单，请确认客户端使用系统 Chrome（内置 Chromium 缺少 h264 支持）")
                    print("  [-] 正在上传视频中...")
                    await asyncio.sleep(3)
                    continue
                button_info = await button.first.get_attribute("class") or ""
                if "weui-desktop-btn_disabled" in button_info:
                    print("  [-] 正在上传视频中...")
                    await asyncio.sleep(3)
                    if await page.locator('div.status-msg.error').count() and await page.locator(
                            'div.media-status-content div.tag-inner:has-text("删除")').count():
                        print("  [-] 发现上传出错了...")
                        await self.handle_upload_error(page)
                    continue
                print("  [-]视频上传完毕")
                break
            except Exception:
                print("  [-] 正在上传视频中...")
                await asyncio.sleep(3)
        else:
            print("  [!] 等待上传完成超时，继续尝试发布")

        # 更换封面：拿不到入口就跳过，不能因此卡住发布
        if not self.video_preview or not os.path.exists(self.video_preview):
            return
        try:
            cover = page.locator('div.finder-tag-wrap.btn:has-text("更换封面")').first
            if not await cover.count():
                print("  [!] 没有封面入口，跳过封面设置")
                return
            await asyncio.sleep(2)
            cover_info = await cover.get_attribute("class") or ""
            if "disabled" in cover_info:
                return
            await cover.click()
            await page.locator('div.single-cover-uploader-wrap > div.wrap').hover()
            if await page.locator(".del-wrap > .svg-icon").count():
                await page.locator(".del-wrap > .svg-icon").click()
            preview_upload_div_loc = page.locator("div.single-cover-uploader-wrap > div.wrap")
            async with page.expect_file_chooser() as fc_info:
                await preview_upload_div_loc.click()
            preview_file_chooser = await fc_info.value
            await preview_file_chooser.set_files(self.video_preview)
            await asyncio.sleep(2)
            await page.get_by_role("button", name="确定").click()
            await asyncio.sleep(1)
            await page.get_by_role("button", name="确认").click()
        except Exception as exc:
            print(f"  [!] 设置封面失败，跳过：{type(exc).__name__}: {exc}")

    async def add_title_tags(self, page):
        editor = page.locator("div.input-editor").first
        if not await editor.count():
            editor = page.locator("div[contenteditable='true']").first
        if not await editor.count():
            raise RuntimeError("未找到视频号的标题/描述输入框，发布页结构可能已变化")
        await editor.click()
        await page.keyboard.type(self.title)
        if self.tags:
            await page.keyboard.press("Enter")
            for index, tag in enumerate(self.tags, start=1):
                await page.keyboard.type("#" + tag)
                await page.keyboard.press("Space")
        print(f"成功添加标题和hashtag: {len(self.tags)}")

    async def add_collection(self, page):
        collection_elements = page.get_by_text("添加到合集").locator("xpath=following-sibling::div").locator(
            '.option-list-wrap > div')
        if await collection_elements.count() > 1:
            await page.get_by_text("添加到合集").locator("xpath=following-sibling::div").click()
            await collection_elements.first.click()

    async def add_location(self, page):
        collection_elements = page.get_by_text("位置").locator("xpath=following-sibling::div").locator(
            '.option-list-wrap > div')
        if await collection_elements.count() > 1:
            await page.get_by_text("添加到合集").locator("xpath=following-sibling::div").click()
            await collection_elements.first.click()

    async def add_original(self, page):
        if await page.get_by_label("声明后，作品将展示原创标记，有机会获得广告收入。").count():
            await page.get_by_label("声明后，作品将展示原创标记，有机会获得广告收入。").check()
        # 检查 "我已阅读并同意《原创声明须知》和《使用条款》。如滥用声明，平台将驳回并予以相关处置。" 元素是否存在
        label_locator = await page.get_by_text("我已阅读并同意《原创声明须知》和《使用条款》。如滥用声明，平台将驳回并予以相关处置。").first.is_visible()
        if label_locator:
            await page.locator('div.declare-original-dialog input.ant-checkbox-input').first.check()
        #     await page.get_by_role("button", name="声明原创").click()
        # 2023年11月20日 wechat更新: 可能新账号或者改版账号，出现新的选择页面
        # 选择原创分类
        if self.category:
            # 因处罚无法勾选原创，故先判断是否可用 这里先忽略 TODO
            # if  await page.locator('div.declare-original-checkbox input.ant-checkbox-input:visible').count() and not await page.locator('div.declare-original-checkbox input.ant-checkbox-input').is_disabled():
            #     await page.locator('div.declare-original-checkbox input.ant-checkbox-input').click()
            # if  await page.locator(
            #         'div.declare-original-dialog label.ant-checkbox-wrapper.ant-checkbox-wrapper-checked:visible').count():
            #     await page.locator('div.declare-original-dialog input.ant-checkbox-input:visible').click()
            if await page.locator('div.original-type-form > div.form-label:has-text("原创类型"):visible').count():
                await page.locator('div.form-content:visible').click()  # 下拉菜单
                # await page.locator("#container-wrap").get_by_role("list").locator("div").filter(has_text=f"{self.category} {self.category}").first.click()
                await page.locator(f'div.form-content:visible ul.weui-desktop-dropdown__list li.weui-desktop-dropdown__list-ele:has-text("{self.category}")').first.click()
                await asyncio.sleep(1)
                # if 'semi-switch-checked' not in await page.eval_on_selector(third_part_element, 'div => div.className'):
        # 能点击按钮就点击
        submit_button_info = await page.get_by_role("button", name="声明原创").get_attribute(
            'class')
        if "weui-desktop-btn_disabled" not in submit_button_info:
            await page.get_by_role("button", name="声明原创").click()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
