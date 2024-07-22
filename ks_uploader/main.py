# -*- coding: utf-8 -*-
import asyncio
import redis
import traceback
from datetime import datetime
from conf import REDIS_CONF
from playwright.async_api import Playwright, async_playwright


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
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


def cache_data(key: str, value: str, timeout=60) -> None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],
                                   password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.set(key, value)
    redis_client.expire(key, timeout)


def cache_get_data(key: str) -> None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],
                                   password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    data = redis_client.get(key)
    if data is not None:
        # 解码bytes为字符串，这里假设数据是utf-8编码的  
        data_str = data.decode('utf-8')
        return data_str
    else:
        return ""


def cache_delete(key: str) -> None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],
                                   password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.delete(key)


async def ks_cookie_gen(account_file_path, account_id="", queue_id=""):
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
            await page.goto(url="https://passport.kuaishou.com/pc/account/login/?sid=kuaishou.web.cp.api&callback=https%3A%2F%2Fcp.kuaishou.com%2Frest%2Finfra%2Fsts%3FfollowUrl%3Dhttps%253A%252F%252Fcp.kuaishou.com%252Fprofile%26setRootDomain%3Dtrue", timeout=20000)
            # await page.wait_for_url(url="https://creator.douyin.com/",timeout=10000)
            await page.locator('div.platform-switch').click()
            # base64搞定
            img_element = page.get_by_role("img", name="qrcode")
            await img_element.wait_for()
            img_element_src = await img_element.get_attribute(name="src", timeout=10000)
            cache_data(f"ks_login_ewm_{queue_id}", img_element_src)
            num = 1
            while True:
                await asyncio.sleep(3)
                # 判断是否跳转到登陆后链接，如果有跳出循环
                if 'cp.kuaishou.com/profile' in page.url:
                    break
                # 这里先取消身份认证
                # auth_div = False
                auth_visible = False
                if auth_visible:
                    # 说明需要验证码
                    cache_data(f"ks_login_need_auth_{queue_id}", 1)
                    # 点击接收短信验证码
                    await page.get_by_text("接收短信验证").click()
                    # 等一秒后
                    await asyncio.sleep(1)
                    # 点击验证码
                    await page.get_by_text("获取验证码").click()
                    num_two = 1
                    while True:
                        await asyncio.sleep(3)
                        # 判断是否获取到了缓存中的验证码
                        auth_number = cache_get_data(f"ks_login_authcode_{queue_id}")
                        if auth_number:
                            await page.get_by_placeholder('请输入验证码').nth(1).fill(auth_number)
                            # 然后点击验证按钮
                            await page.get_by_text("验证", exact=True).click()
                            await asyncio.sleep(2)
                            # 验证后删除需要验证码缓存
                            cache_delete(f"ks_login_need_auth_{queue_id}")
                            break
                        if num_two > 20:
                            # 输入验证码
                            break
                        # 多循环一次
                        num_two += 1
                if num > 13:
                    break
                num += 1
            # 判断cookie长度过短说明没登录，无需保存
            cookies = await context.cookies()
            # 默认没获取到用户信息
            user_info = False
            # 保存cookie长度不大于0不保存
            if len(cookies) > 0:
                # 直接获取用户数据然后返回
                third_id_cont = await page.get_by_text("快手号：").inner_text()
                third_id = third_id_cont.split("：")[1]
                user_info = {
                    'account_id': third_id,  # 抖音号
                    'username': await page.locator(".personal-info__detail div.detail__name").inner_text(),  # 用户名
                    'avatar': await page.locator(".personal-info__detail div.detail__row img").nth(0).get_attribute("src")  # 头像
                }
                account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
                # 保存cookie
                await context.storage_state(path=account_file)
                # 保存当前用户的登录状态，临时用来检测登陆状态用，只保存60s的状态检测
                cache_data(f"ks_login_status_{account_id}", 1, 60)
                # 保存抖音账号的登录状态，时间一个周
                cache_data(f"ks_login_status_third_{account_id}_{third_id}", 1, 604800)
            # 关闭浏览器
            await context.close()
            await browser.close()
            await playwright.stop()
            return user_info
    except:
        traceback.print_exc()
        return False
class KuaiShouVideo(object):
    def __init__(self, title, file_path, video_preview, tags, publish_date, account_file, location="重庆市"):
        self.title = title  # 视频标题
        self.file_path = file_path # 视频文件
        self.video_preview = video_preview # 视频预览图
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
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
            browser = await playwright.chromium.launch(headless=False, executable_path=self.local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=False)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        print('[+]正在上传-------{}'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        print('[-] 正在打开主页...')
        await page.wait_for_url("https://cp.kuaishou.com/article/publish/video")
        # 点击 "上传视频" 按钮
        upload_div_loc = page.get_by_role("button", name="上传视频")
        # await upload_div_loc.wait_for()
        async with page.expect_file_chooser() as fc_info:
            await upload_div_loc.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)
        # 等待页面跳转到指定的 URL
        await asyncio.sleep(1)
        known_button = page.get_by_role("button", name="我知道了")
        if await known_button.count():
           await known_button.click()
        # 填充标题和话题
        await asyncio.sleep(1)
        print("  [-] 正在填充标题和话题...")
        title_container = page.get_by_placeholder('添加合适的话题和描述，作品能获得更多推荐～')
        if await title_container.count():
           await title_container.click()
           await title_container.fill(self.title[:30])
        # else:
        #     titlecontainer = page.locator(".notranslate")
        #     await titlecontainer.click()
        #     print("clear existing title")
        #     await page.keyboard.press("Backspace")
        #     await page.keyboard.press("Control+KeyA")
        #     await page.keyboard.press("Delete")
        #     print("filling new  title")
        #     await page.keyboard.type(self.title)
        #     await page.keyboard.press("Enter")
        # css_selector = ".zone-container"
        # for index, tag in enumerate(self.tags, start=1):
        #     print("正在添加第%s个话题" % index)
        #     await page.type(css_selector, "#" + tag)
        #     await page.press(css_selector, "Space")

        while True:
            # 判断重新上传按钮是否存在，如果不存在，代表视频正在上传，则等待
            try:
                #  新版：定位重新上传
                number = await page.locator('span:has-text("上传成功")').count()
                if number > 0:
                    print("  [-]视频上传完毕")
                    break
                else:
                    print("  [-] 正在上传视频中...")
                    await asyncio.sleep(2)

                    # if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                    #     print("  [-] 发现上传出错了...")
                    #     await self.handle_upload_error(page)
            except:
                print("  [-] 正在上传视频中...")
                await asyncio.sleep(2)

        # 修改预览图
        await page.get_by_role("button", name="编辑封面").click()
        await asyncio.sleep(1)
        await page.get_by_role("tab", name="上传封面").click()
        preview_upload_div_loc = page.get_by_role("tabpanel", name="上传封面").locator("div").nth(1)
        # await upload_div_loc.wait_for()
        async with page.expect_file_chooser() as fc_info:
            await preview_upload_div_loc.click()
        preview_file_chooser = await fc_info.value
        await preview_file_chooser.set_files(self.video_preview)
        await page.get_by_role("button", name="确认").click()
        await asyncio.sleep(5)  # 这里延迟是为了方便预览图上传
        # 定时发布
        # if self.publish_date != 0:
        #     await self.set_schedule_time_ks(page, self.publish_date)

        # 判断视频是否发布成功
        while True:
            # 判断视频是否发布成功
            try:
                publish_button = page.get_by_role('button', name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url("https://cp.kuaishou.com/article/manage/video?status=2&from=publish",
                                        timeout=1500)  # 如果自动跳转到作品页面，则代表发布成功
                print("  [-]视频发布成功")
                break
            except:
                print("  [-] 视频正在发布中...")
                await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

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


