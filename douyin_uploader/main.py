# -*- coding: utf-8 -*-
import asyncio
import re
import time
import traceback  
import os
from datetime import datetime
from playwright.async_api import Playwright, async_playwright
from utils.cache_store import cache_data, cache_get_data, cache_delete
from utils.browser_mode import (
    CHROME_ARGS, apply_stealth, context_kwargs, headless_enabled,
)
from utils.login_diag import report, report_exc

# 登录态判定：抖音扫码成功后必然下发下列会话 cookie，比识别页面元素稳定得多
DOUYIN_SESSION_COOKIES = ("sessionid", "sessionid_ss", "sid_tt", "sid_guard")
# 扫码等待上限（秒）：给用户足够时间扫码 + 可能的短信验证
LOGIN_TIMEOUT = 300
# 最近一次登录失败的原因，桌面端会读取它展示给用户
LAST_LOGIN_ERROR = ""

async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel="chromium")
        context = await browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        try:
            await page.wait_for_selector("div.boards-more h3:text('抖音排行榜')", timeout=5000)  # 等待5秒
            print("[+] 等待5秒 cookie 失效")
            return False
        except:
            print("[+] cookie 有效")
            return True


async def douyin_setup(account_file_path, handle=False,account_id="",queue_id=""):
    user_info = await douyin_cookie_gen(account_file_path,account_id,queue_id)
    return user_info

def _has_douyin_session(cookies) -> bool:
    names = {cookie.get("name") for cookie in cookies or []}
    return any(name in names for name in DOUYIN_SESSION_COOKIES)


async def _save_douyin_qrcode(page, queue_id):
    """把二维码地址写进缓存（供远程前端展示），桌面端取不到也不影响登录。

    抖音改版频繁，二维码容器的 class 名随时会变，所以这里逐个试候选选择器，
    全失败就跳过——浏览器窗口里本来就摆着二维码，用户直接扫即可。
    """
    for selector in (
        "div[class*='qrcode'] img",
        "img[class*='qrcode']",
        "div[class*='login-card'] img[src^='data:image']",
    ):
        try:
            locator = page.locator(selector).first
            await locator.wait_for(state="visible", timeout=3000)
            src = await locator.get_attribute("src")
            if src:
                cache_data(f"douyin_login_ewm_{queue_id}", src)
                return
        except Exception:
            continue


async def _read_douyin_identity(page, cookies) -> dict:
    """读取昵称 / 抖音号 / 头像。

    任何一项读不到都只是留空，绝不让登录流程失败——cookie 才是发布真正需要的东西。
    """
    third_id = ""
    username = ""
    avatar = ""

    # 1) 创作者中心自带接口，最准；注意返回结构是 {..., "user": {...}}
    #    （以前读的是 user_info，平台改版后一直取空，昵称才会退化成抖音号数字）
    try:
        data = await page.evaluate(
            "async () => {"
            "  try {"
            "    const r = await fetch('/web/api/media/user/info/', {credentials: 'include'});"
            "    if (!r.ok) return null;"
            "    return await r.json();"
            "  } catch (e) { return null; }"
            "}"
        )
        payload = data or {}
        info = payload.get("user") or payload.get("user_info") or {}
        username = str(info.get("nickname") or "").strip()
        third_id = str(info.get("unique_id") or info.get("short_id") or "").strip()
        avatar_info = info.get("avatar_larger") or info.get("avatar_medium") or {}
        urls = avatar_info.get("url_list") or []
        avatar = str(urls[0]) if urls else str(info.get("avatar_uri") or "")
    except Exception:
        pass

    # 2) 整页文本里正则找"抖音号：xxx"，不依赖任何 class 名
    if not third_id:
        try:
            text = await page.evaluate("() => (document.body && document.body.innerText) || ''")
            match = re.search(r"抖音号[:：]\s*([A-Za-z0-9_.\-]{3,})", text or "")
            if match:
                third_id = match.group(1)
        except Exception:
            pass

    # 3) 页面上的昵称 / 头像
    if not username:
        for selector in (
            "[data-e2e='user-info-name']",
            "div[class*='nickname']",
            "span[class*='name-']",
        ):
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
            locator = page.locator("div[class*='avatar'] img").first
            if await locator.count():
                avatar = await locator.get_attribute("src") or ""
        except Exception:
            pass

    # 4) 兜底：cookie 里的用户 id，保证 third_id 一定有个值
    if not third_id:
        for name in ("uid_tt", "uid_tt_ss", "sid_tt"):
            for cookie in cookies or []:
                if cookie.get("name") == name and cookie.get("value"):
                    third_id = str(cookie["value"])
                    break
            if third_id:
                break

    return {"account_id": third_id, "username": username, "avatar": avatar}


async def _finalize_douyin_login(context, page, account_file_path, account_id) -> dict:
    """登录成功后收尾：等后台首页渲染、读账号信息、落盘 storage_state。"""
    try:
        await page.wait_for_url("**/creator-micro/**", timeout=15000)
    except Exception:
        pass
    await asyncio.sleep(2)

    cookies = await context.cookies()
    user_info = await _read_douyin_identity(page, cookies)

    third_id = user_info.get("account_id") or ""
    if not third_id:
        third_id = f"dy{int(time.time())}"
        user_info["account_id"] = third_id
        report("未能读取到抖音号，已用临时 ID 代替（不影响发布）", "WARN")

    if not user_info.get("username"):
        user_info["username"] = third_id

    account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
    await context.storage_state(path=account_file)
    # 历史缓存键，保留以兼容原服务端逻辑
    cache_data(f"douyin_login_status_{account_id}", 1, 60)
    cache_data(f"douyin_login_status_third_{account_id}_{third_id}", 1, 604800)
    return user_info


async def douyin_cookie_gen(account_file_path, account_id="", queue_id=""):
    """打开浏览器扫码登录抖音，成功后保存 storage_state 并返回账号信息。

    与原实现的区别：登录成功与否用会话 cookie 判定（原先依赖页面上"抖音号："
    和写死的 class 名，平台一改版就必然失败）。
    """
    global LAST_LOGIN_ERROR
    LAST_LOGIN_ERROR = ""

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/", timeout=30000)

            await _save_douyin_qrcode(page, queue_id)
            report("抖音登录页已打开，请用抖音 App 扫码登录")

            logged_in = False
            hinted_auth = False
            deadline = time.time() + LOGIN_TIMEOUT
            while time.time() < deadline:
                await asyncio.sleep(2)
                try:
                    cookies = await context.cookies()
                except Exception:
                    LAST_LOGIN_ERROR = "登录窗口被关闭了，请重新点击「去登录」"
                    report(LAST_LOGIN_ERROR, "WARN")
                    return False

                if _has_douyin_session(cookies):
                    logged_in = True
                    break

                try:
                    if "creator-micro" in page.url:
                        logged_in = True
                        break
                except Exception:
                    pass

                # 需要短信验证时提示用户直接在浏览器里操作，不再自动点按钮
                if not hinted_auth:
                    try:
                        if await page.get_by_text("身份验证").first.is_visible():
                            hinted_auth = True
                            report("抖音要求身份验证，请在浏览器窗口里完成短信验证", "WARN")
                    except Exception:
                        pass

            if not logged_in:
                LAST_LOGIN_ERROR = f"等待扫码超时（{LOGIN_TIMEOUT} 秒），没有检测到登录状态"
                report(LAST_LOGIN_ERROR, "ERROR")
                return False

            report("已检测到抖音登录成功，正在保存登录信息…")

            user_info = await _finalize_douyin_login(context, page, account_file_path, account_id)

            await context.close()
            await browser.close()
            report(f"抖音账号已保存：{user_info.get('username')}（{user_info.get('account_id')}）")
            return user_info
    except Exception as exc:
        LAST_LOGIN_ERROR = f"{type(exc).__name__}: {exc}"
        report_exc("抖音登录失败", exc)
        return False

async def douyin_cookie_gen_home(account_file_path,account_id="",queue_id=""):
    try:
        async with async_playwright() as playwright:
            options = {
                'headless': False
            }
            # Make sure to run headed.
            browser = await playwright.chromium.launch(**options)
            # Setup context however you like.
            context = await browser.new_context()  # Pass any options
            # Pause the page, and start recording manually.
            page = await context.new_page()
            await page.goto(url="https://www.douyin.com/")
            await page.wait_for_url("https://www.douyin.com/",timeout=10000)
            # base64搞定
            login_btn = page.get_by_role("button", name="登录")
            await login_btn.click()
            img_element = page.locator('img.web-login-scan-code__content__qrcode-wrapper__qrcode')
            img_element_src = await img_element.get_attribute(name="src",timeout=10000)
            cache_data(f"douyin_login_ewm_{queue_id}",img_element_src)
            # 截图然后返回给前端
            # await asyncio.sleep(3)  # 过3秒时间再截图
            # await page.screenshot(path=f"{account_id}_douyin_screenshot.png")
            # await asyncio.sleep(40)  # 给用户40秒时间进行扫码登录
            # 等待过程换成循环，然后同时检测状态
            success_div = page.get_by_text("扫码成功")
            is_visible = await success_div.is_visible(timeout=50000)
            num = 1
            while True:
                await asyncio.sleep(3)
                # 判断是否有已扫码显示，如果有跳出循环
                is_visible = await success_div.is_visible()
                if is_visible:
                    # 保存记录一下说明已经扫码
                    cache_data(f"douyin_login_scan_{queue_id}",1,6)
                    break
                if num > 13:
                    break
                num+=1
            # 等待用户点击，再过6秒刷新页面然后保存cookie
            await asyncio.sleep(6)
            # 判断cookie长度过短说明没登录，无需保存
            cookies = await context.cookies()
            # 默认没获取到用户信息
            user_info = False
            # 保存cookie长度不大于36不保存
            if len(cookies) > 36:
                # 打开用户中心，选择用户数据然后返回
                page = await context.new_page()
                await page.goto("https://www.douyin.com/user/self")
                await page.wait_for_url("https://www.douyin.com/user/self")
                third_id_cont = await page.get_by_text("抖音号：").inner_text()
                third_id = third_id_cont.split("：")[1]
                user_info = {
                    'account_id':third_id,#抖音号
                    'username':await page.locator("h1").inner_text(),#用户名
                    'avatar':await page.locator("div.avatar-component-avatar-container img").nth(2).get_attribute("src")#头像
                }
                account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
                # 保存cookie
                await context.storage_state(path=account_file)
                # 保存当前用户的登录状态，临时用来检测登陆状态用，只保存60s的状态检测
                cache_data(f"douyin_login_status_{account_id}",1,60)
                # 保存抖音账号的登录状态，时间一个周
                cache_data(f"douyin_login_status_third_{account_id}_{third_id}",1,604800)
            # 关闭浏览器
            await context.close()
            await browser.close()
            await playwright.stop()
            return user_info
    except:
        return False

class DouYinVideo(object):
    def __init__(self, title, file_path,preview_path, tags, publish_date, account_file,location="重庆市",description=""):
        self.title = title  # 视频标题
        self.file_path = file_path # 视频文件路径
        self.preview_path = preview_path # 视频预览图路径
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.description = description  # 作品描述（与标题分开填）
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = ""  # change me
        self.location = location

    async def set_schedule_time_douyin(self, page, publish_date):
        # 选择包含特定文本内容的 label 元素
        label_element = page.locator("label.radio-d4zkru:has-text('定时发布')")
        # 在选中的 label 元素下点击 checkbox
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        
        await asyncio.sleep(1)
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")

        await asyncio.sleep(1)

    async def handle_upload_error(self, page):
        print("视频出错了，重新上传中")
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        headless = headless_enabled()
        launch_kwargs = {"headless": headless}
        if headless:
            # 不做这层伪装，抖音在无头下会直接弹短信验证，发布点不出去
            launch_kwargs["args"] = CHROME_ARGS
        if self.local_executable_path:
            launch_kwargs["executable_path"] = self.local_executable_path
        browser = await playwright.chromium.launch(**launch_kwargs)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(
            storage_state=f"{self.account_file}", **context_kwargs(browser, headless))
        if headless:
            await apply_stealth(context)

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        print('[+]正在上传-------{}.mp4'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        print('[-] 正在打开主页...')
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")
        if "passport" in page.url or "/login" in page.url:
            raise RuntimeError("抖音登录已失效，请到账号页重新扫码登录")
        if not os.path.exists(self.file_path):
            print(f"上传的视频文件不存在，路径是{self.file_path}")
            # 关闭浏览器上下文和浏览器实例
            await context.close()
            await browser.close()
            await playwright.stop()
            return False

        # 直接给 input[type=file] 塞文件。上传区容器的 class 是哈希值
        # （旧代码写死的 container-drag-info-Tl0RGH 早就换了），不能用来定位。
        file_input = page.locator("input[type=file]").first
        await file_input.wait_for(state="attached", timeout=30000)
        await file_input.set_input_files(self.file_path)
        print("  [-] 已提交视频文件，等待进入发布页...")

        # 发布页 URL 后面带 enter_from 参数，用正则匹配更稳
        await page.wait_for_url(re.compile(r"/content/post/"), timeout=180000)

        # 填充标题和话题
        await asyncio.sleep(1)
        print("  [-] 正在填充标题和话题...")
        title_input = page.locator("input[placeholder*='作品标题']").first
        if await title_input.count():
            await title_input.fill(self.title[:30])
        else:
            # 老版结构：作品标题右侧第一个 div 里的 input
            title_container = page.get_by_text('作品标题').locator("..").locator(
                "xpath=following-sibling::div[1]").locator("input")
            if await title_container.count():
                await title_container.fill(self.title[:30])

        zone = page.locator(".zone-container").first
        if not await zone.count():
            zone = page.locator("div[contenteditable='true']").first
        if await zone.count():
            await zone.click()
            if self.description:
                await page.keyboard.type(self.description[:28])
                await page.keyboard.press("Space")
            for index, tag in enumerate(self.tags, start=1):
                print("正在添加第%s个话题" % index)
                await page.keyboard.type("#" + tag)
                await page.keyboard.press("Space")

        # 等上传结束。「取消上传」还在就说明仍在传输；「上传成功」一闪而过、
        # 「重新上传」在传输过程中也会出现，都不能单独当判据。
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                text = await page.evaluate("() => (document.body && document.body.innerText) || ''")
            except Exception:
                text = ""
            if "上传失败" in text:
                print("  [-] 发现上传出错了，重新上传...")
                await self.handle_upload_error(page)
                await asyncio.sleep(3)
                continue
            if "取消上传" not in text and ("重新上传" in text or "上传成功" in text):
                print("  [-] 视频上传完毕")
                break
            print("  [-] 正在上传视频中...")
            await asyncio.sleep(3)
        # 点击去掉我知道了
        known_count = await page.get_by_role("button", name="我知道了").count()
        if known_count > 0:
           await page.get_by_role("button", name="我知道了").nth(0).click()
        await asyncio.sleep(2)
        # await page.get_by_text("选择封面").click()
        # await asyncio.sleep(1)
        # await page.get_by_text("上传封面").click()
        # await asyncio.sleep(3)
        # preview_upload_div_loc = page.locator("div.semi-upload-drag-area")
        # # await upload_div_loc.wait_for()
        # async with page.expect_file_chooser() as fc_info:
        #     await preview_upload_div_loc.click()
        # preview_file_chooser = await fc_info.value
        # await preview_file_chooser.set_files(self.preview_path)
        # await asyncio.sleep(3)
        # await page.get_by_role("button", name="完成").click()
        # 处理完预览图后
        # 位置：拿不到就跳过，不能让整个发布挂在这里
        if self.location:
            try:
                loc = page.locator("div.semi-select").filter(has_text="输入地理位置").first
                if not await loc.count():
                    loc = page.get_by_text("输入地理位置").first
                if await loc.count():
                    await loc.click()
                    await asyncio.sleep(1)
                    await page.keyboard.press("Control+KeyA")
                    await page.keyboard.press("Delete")
                    await page.keyboard.type(self.location)
                    await asyncio.sleep(1.5)
                    option = page.locator('div[role="listbox"] [role="option"]').first
                    if await option.count():
                        await option.click()
                    else:
                        print("  [!] 没有匹配的位置候选，跳过位置设置")
                else:
                    print("  [!] 未找到位置输入框，跳过位置设置")
            except Exception as exc:
                print(f"  [!] 设置位置失败，跳过：{type(exc).__name__}: {exc}")

        # 頭條/西瓜
        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        # 定位是否有第三方平台
        if await page.locator(third_part_element).count():
            # 检测是否是已选中状态
            if 'semi-switch-checked' not in await page.eval_on_selector(third_part_element, 'div => div.className'):
                await page.locator(third_part_element).locator('input.semi-switch-native-control').click()

        # 定时发布
        if self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        # 点击发布。平台允许上传中直接发布，成功后会自动跳到作品管理页
        publish_button = page.get_by_role('button', name="发布", exact=True)
        if not await publish_button.count():
            raise RuntimeError("未找到「发布」按钮，发布页结构可能已变化")
        if os.environ.get("MATRIX_DRY_RUN") == "1":
            print("  [!] 干跑模式：已就绪到发布按钮，不实际点击发布")
            await context.storage_state(path=self.account_file)
            await context.close()
            await browser.close()
            await playwright.stop()
            return True
        await publish_button.first.click()
        print("  [-] 已点击发布，等待结果...")

        ok = False
        deadline = time.time() + 300
        shot_dir = os.environ.get("MATRIX_DEBUG_SHOT") or ""
        tick = 0
        while time.time() < deadline:
            if "/content/manage" in page.url:
                ok = True
                break
            try:
                text = await page.evaluate("() => (document.body && document.body.innerText) || ''")
            except Exception:
                text = ""
            tick += 1
            if shot_dir and tick % 3 == 0:
                try:
                    os.makedirs(shot_dir, exist_ok=True)
                    await page.screenshot(path=os.path.join(shot_dir, "dy_%d.png" % int(time.time())))
                    print("  [dbg] url=%s | %s" % (page.url[-60:], text[:160].replace("\n", " ")), flush=True)
                except Exception:
                    pass
            if "发布失败" in text or "提交失败" in text:
                raise RuntimeError("平台提示发布失败，请到创作者后台查看原因")
            # 无头环境易触发风控：会弹「接收短信验证码」，不处理会一直卡在发布页
            if "短信验证" in text or "安全验证" in text or "身份验证" in text:
                raise RuntimeError(
                    "抖音要求短信验证码，自动化无法完成；请把 MATRIX_HEADLESS 设为 0 用有头模式发布一次，"
                    "手动完成验证后再恢复无头")
            await asyncio.sleep(2)

        if ok:
            print("  [-]视频发布成功")
        else:
            # 不当作失败：可能已经发布成功只是没跳转，重试会造成重复作品
            report("发布后 5 分钟没有跳转到作品管理页，请到后台确认是否已发布", "WARN")
        await context.storage_state(path=self.account_file)  # 保存cookie
        print('  [-]cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()
        await playwright.stop()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)


