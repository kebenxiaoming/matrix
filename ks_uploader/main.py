# -*- coding: utf-8 -*-
import asyncio
import os
import re
import time
import traceback
from datetime import datetime
from playwright.async_api import Playwright, async_playwright
from utils.cache_store import cache_data, cache_get_data, cache_delete
from utils.browser_login import LoginAborted, grab_qrcode, pick_id_by_cookies, wait_for_login
from utils.browser_mode import headless_enabled
from utils.login_diag import report, report_exc

KS_LOGIN_URL = (
    "https://passport.kuaishou.com/pc/account/login/?sid=kuaishou.web.cp.api"
    "&callback=https%3A%2F%2Fcp.kuaishou.com%2Frest%2Finfra%2Fsts%3FfollowUrl%3D"
    "https%253A%252F%252Fcp.kuaishou.com%252Fprofile%26setRootDomain%3Dtrue"
)
LOGIN_TIMEOUT = 300
# 最近一次登录失败原因，桌面端会读取展示
LAST_LOGIN_ERROR = ""


async def _read_ks_identity(page, cookies) -> dict:
    """读取快手号 / 昵称 / 头像；任何一项读不到都只留空。

    昵称走 DOM：后台顶部是 ``.user-name`` / ``.user-info-name``；
    接口 ``/rest/cp/creator/pc/home/userInfo`` 需要 ``__NS_sig3`` 签名，直接 fetch
    会被拒（result=10001），所以不依赖它。
    """
    third_id = ""
    username = ""
    avatar = ""

    try:
        text = await page.evaluate("() => (document.body && document.body.innerText) || ''")
        match = re.search(r"快手号[:：]\s*([A-Za-z0-9_.\-]{3,})", text or "")
        if match:
            third_id = match.group(1)
    except Exception:
        pass

    if not username:
        for selector in (
            ".user-name",
            ".user-info-name",
            ".user__name",
            "div[class*='user-name']",
            "span[class*='user-name']",
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
        for selector in (
            ".user-info img",
            "img[class*='avatar']",
            ".user-name-wrap img",
            "img[class*='head']",
        ):
            try:
                locator = page.locator(selector).first
                if await locator.count():
                    src = await locator.get_attribute("src") or ""
                    if src:
                        avatar = src
                        break
            except Exception:
                continue

    if not third_id:
        third_id = pick_id_by_cookies(cookies, ("userId", "kuaishou.web.cp.api_ph"))

    return {"account_id": third_id, "username": username, "avatar": avatar}


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel="chromium")
        context = await browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/profile")
        try:
            await page.wait_for_selector(".personal-info div.detail__userKwaiId:has-text('快手号')", timeout=5000)  # 等待5秒
            print("[+] 等待5秒 cookie 失效")
            return False
        except:
            print("[+] cookie 有效")
            return True


async def ks_setup(account_file_path, handle=False, account_id="", queue_id=""):
    user_info = await ks_cookie_gen(account_file_path, account_id, queue_id)
    return user_info


async def ks_cookie_gen(account_file_path, account_id="", queue_id=""):
    global LAST_LOGIN_ERROR
    LAST_LOGIN_ERROR = ""
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
            await page.goto(KS_LOGIN_URL, timeout=30000)

            # 切到扫码登录（元素变了也继续，用户可以在窗口里自己点）
            try:
                await page.locator('div.platform-switch').click(timeout=8000)
            except Exception:
                pass
            await grab_qrcode(
                page, "ks_login_ewm_{queue_id}",
                ("img[alt='qrcode']", "img[class*='qrcode']", "img[src^='data:image']"),
                cache_data, queue_id,
            )
            report("快手登录页已打开，请用快手 App 扫码登录")

            ok = await wait_for_login(
                context, page,
                url_tokens=("cp.kuaishou.com/profile",),
                timeout=LOGIN_TIMEOUT,
            )
            if not ok:
                LAST_LOGIN_ERROR = f"等待扫码超时（{LOGIN_TIMEOUT} 秒），没有检测到登录状态"
                report(LAST_LOGIN_ERROR, "ERROR")
                return False

            report("已检测到快手登录成功，正在保存登录信息…")
            try:
                await page.wait_for_url("**/cp.kuaishou.com/profile**", timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(2)

            cookies = await context.cookies()
            user_info = await _read_ks_identity(page, cookies)

            third_id = user_info.get("account_id") or ""
            if not third_id:
                third_id = f"ks{int(time.time())}"
                user_info["account_id"] = third_id
                report("未能读取到快手号，已用临时 ID 代替（不影响发布）", "WARN")
            if not user_info.get("username"):
                user_info["username"] = third_id

            account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
            await context.storage_state(path=account_file)
            cache_data(f"ks_login_status_{account_id}", 1, 60)
            cache_data(f"ks_login_status_third_{account_id}_{third_id}", 1, 604800)

            await context.close()
            await browser.close()
            report(f"快手账号已保存：{user_info['username']}（{third_id}）")
            return user_info
    except LoginAborted as exc:
        LAST_LOGIN_ERROR = str(exc)
        report(LAST_LOGIN_ERROR, "WARN")
        return False
    except Exception as exc:
        LAST_LOGIN_ERROR = f"{type(exc).__name__}: {exc}"
        report_exc("快手登录失败", exc)
        return False


class KuaiShouVideo(object):
    def __init__(self, title, file_path, video_preview, tags, publish_date, account_file, location="重庆市", description=""):
        self.title = title  # 视频标题
        self.file_path = file_path # 视频文件
        self.video_preview = video_preview # 视频预览图
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.description = description
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = ""  # change me
        self.location = location

    async def set_schedule_time_ks(self, page, publish_date):
        # 选择包含特定文本内容的 label 元素
        label_element = page.locator("label.radio--4Gpx6:has-text('定时发布')")
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
        if self.local_executable_path:
            browser = await playwright.chromium.launch(headless=headless_enabled(), executable_path=self.local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=headless_enabled())
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        print('[+]正在上传-------{}'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        print('[-] 正在打开主页...')
        try:
            await page.wait_for_url("https://cp.kuaishou.com/article/publish/video", timeout=20000)
        except Exception:
            if "passport" in page.url or "login" in page.url:
                raise RuntimeError("快手登录已失效，请到账号页重新扫码登录")
            raise
        if "passport" in page.url or "login" in page.url:
            raise RuntimeError("快手登录已失效，请到账号页重新扫码登录")
        # 直接给 input[type=file] 塞文件，不依赖按钮文案和文件选择框
        file_input = page.locator("input[type=file]").first
        await file_input.wait_for(state="attached", timeout=30000)
        await file_input.set_input_files(self.file_path)
        print("  [-] 已提交视频文件")

        known_button = page.get_by_role("button", name="我知道了")
        if await known_button.count():
            try:
                await known_button.first.click()
            except Exception:
                pass

        # 描述框：新版是 contenteditable 的 div，placeholder 为「作品描述不会写？试试智能文案」
        # （旧 placeholder『添加合适的话题和描述…』已经不存在）
        # 编辑页要等视频开始上传才会渲染出来，先等元素出现
        try:
            await page.wait_for_selector(
                "div[placeholder*='作品描述'], div[contenteditable='true']", timeout=60000
            )
        except Exception:
            print("  [!] 等待编辑页超时")
        editor = page.locator("div[placeholder*='作品描述']").first
        if not await editor.count():
            editor = page.locator("div[contenteditable='true']").first
        if await editor.count():
            try:
                await editor.click()
                await page.keyboard.type(self.title[:30])
                if self.description:
                    await page.keyboard.type(" " + self.description[:40])
                for index, tag in enumerate(self.tags, start=1):
                    print("正在添加第%s个话题" % index)
                    await page.keyboard.type(" #" + tag)
                print("  [-] 已填标题和话题")
            except Exception as exc:
                print(f"  [!] 填写描述失败：{type(exc).__name__}: {exc}")
        else:
            print("  [!] 未找到作品描述输入框")

        # 快手没有可靠的上传完成标志，这里只等编辑页稳定，成不成交给后面的发布重试
        await asyncio.sleep(5)

        # 修改预览图：新版编辑页不一定有「编辑封面」入口，拿不到就跳过
        try:
            cover_btn = page.get_by_role("button", name="编辑封面")
            if not await cover_btn.count():
                cover_btn = page.get_by_text("编辑封面", exact=True)
            if self.video_preview and os.path.exists(self.video_preview) and await cover_btn.count():
                await cover_btn.first.click()
                await asyncio.sleep(1)
                await page.get_by_role("tab", name="上传封面").click()
                preview_upload_div_loc = page.get_by_role("tabpanel", name="上传封面").locator("div").nth(1)
                async with page.expect_file_chooser() as fc_info:
                    await preview_upload_div_loc.click()
                preview_file_chooser = await fc_info.value
                await preview_file_chooser.set_files(self.video_preview)
                await page.get_by_role("button", name="确认").click()
                await asyncio.sleep(3)
            else:
                print("  [!] 没有可用的封面入口，跳过封面设置")
        except Exception as exc:
            print(f"  [!] 设置封面失败，跳过：{type(exc).__name__}: {exc}")

        # 发布：真正的按钮是底部主按钮（左侧那个 div.publish-button 只是导航项，点了没反应）
        publish_button = page.locator("div[class*='button-primary']").filter(has_text="发布").first
        if not await publish_button.count():
            raise RuntimeError("未找到「发布」主按钮，发布页结构可能已变化")
        if os.environ.get("MATRIX_DRY_RUN") == "1":
            print("  [!] 干跑模式：已就绪到发布按钮，不实际点击发布")
            await context.storage_state(path=self.account_file)
            await context.close()
            await browser.close()
            await playwright.stop()
            return True

        # 快手在上传没结束时点发布会弹「请在视频上传完成后再点击发布」，
        # 而上传过程没有可靠的进度元素，所以这里用"点到不被拒绝为止"。
        ok = False
        deadline = time.time() + 900
        while time.time() < deadline:
            try:
                await publish_button.scroll_into_view_if_needed()
                await publish_button.click()
            except Exception as exc:
                print(f"  [!] 点击发布失败，重试：{type(exc).__name__}")
                await asyncio.sleep(3)
                continue
            await asyncio.sleep(2)

            if "/article/manage" in page.url:
                ok = True
                break

            try:
                body = await page.evaluate("() => (document.body && document.body.innerText) || ''")
            except Exception:
                body = ""
            if "请在视频上传完成后再点击发布" in body:
                print("  [-] 还在上传中，稍后重试…")
                for name in ("确 认", "确认", "确定"):
                    confirm = page.get_by_role("button", name=name)
                    if await confirm.count():
                        try:
                            await confirm.first.click()
                        except Exception:
                            pass
                        break
                await asyncio.sleep(5)
                continue
            if "发布成功" in body:
                ok = True
                break
            await asyncio.sleep(3)

        if ok:
            print("  [-]视频发布成功")
        else:
            report("发布重试 15 分钟仍未成功，请到快手后台确认", "WARN")
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


