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

def cache_data(key:str,value:str,timeout=60)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.set(key, value)
    redis_client.expire(key, timeout)

def cache_get_data(key:str)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    data = redis_client.get(key)
    if data is not None:  
        # 解码bytes为字符串，这里假设数据是utf-8编码的  
        data_str = data.decode('utf-8')  
        return data_str
    else:  
        return ""
def cache_delete(key:str)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.delete(key)

async def douyin_cookie_gen(account_file_path,account_id="",queue_id=""):
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
            await page.goto(url="https://creator.douyin.com/",timeout=20000)
            # await page.wait_for_url(url="https://creator.douyin.com/",timeout=10000)
            await page.locator('span.login').click()
            # base64搞定
            img_element = page.locator('div.qrcode-image-kN3ACJ img:first-child')
            await img_element.wait_for()
            img_element_src = await img_element.get_attribute(name="src",timeout=10000)
            cache_data(f"douyin_login_ewm_{queue_id}",img_element_src)
            # 截图然后返回给前端
            # await asyncio.sleep(3)  # 过3秒时间再截图
            # await page.screenshot(path=f"{account_id}_douyin_screenshot.png")
            # 检测当前url链接是否是https://creator.douyin.com/creator-micro/home
            num = 1
            while True:
                await asyncio.sleep(3)
                # 判断是否有已扫码显示，如果有跳出循环
                print(page.url)
                if 'creator.douyin.com/creator-micro/home' in page.url:
                    break
                # 判断是否要身份认证
                auth_div = page.get_by_text("身份验证")
                auth_visible = await auth_div.is_visible()
                if auth_visible:
                    # 说明需要验证码
                    cache_data(f"douyin_login_need_auth_{queue_id}",1)
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
                        auth_number = cache_get_data(f"douyin_login_authcode_{queue_id}")
                        if auth_number:
                            await page.get_by_placeholder('请输入验证码').nth(1).fill(auth_number)
                            # 然后点击验证按钮
                            await page.get_by_text("验证", exact=True).click()
                            await asyncio.sleep(2)
                            # 验证后删除需要验证码缓存
                            cache_delete(f"douyin_login_need_auth_{queue_id}")
                            break
                        if num_two > 20:
                            # 输入验证码
                            break
                        # 多循环一次
                        num_two+=1
                if num > 13:
                    break
                num+=1
            # 判断cookie长度过短说明没登录，无需保存
            cookies = await context.cookies()
            # 默认没获取到用户信息
            user_info = False
            # 保存cookie长度不大于30不保存
            if len(cookies) > 30:
                # 直接获取用户数据然后返回
                third_id_cont = await page.get_by_text("抖音号：").inner_text()
                third_id = third_id_cont.split("：")[1]
                user_info = {
                    'account_id':third_id,#抖音号
                    'username':await page.locator("div.rNsML").inner_text(),#用户名
                    'avatar':await page.locator("div.t4cTN img").nth(0).get_attribute("src")#头像
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
        traceback.print_exc()
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
    def __init__(self, title, file_path, tags, publish_date: datetime, account_file,location="重庆市"):
        self.title = title  # 视频标题
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = ""  # change me
        self.location = location

    async def set_schedule_time_douyin(self, page, publish_date):
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
            browser = await playwright.chromium.launch(headless=True, executable_path=self.local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=True)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        print('[+]正在上传-------{}.mp4'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        print('[-] 正在打开主页...')
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")
        # 点击 "上传视频" 按钮
        await page.locator(".upload-btn--9eZLd").set_input_files(self.file_path)

        # 等待页面跳转到指定的 URL
        while True:
            # 判断是是否进入视频发布页面，没进入，则自动等待到超时
            try:
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page")
                break
            except:
                print("  [-] 正在等待进入视频发布页面...")
                await asyncio.sleep(0.1)

        # 填充标题和话题
        # 检查是否存在包含输入框的元素
        # 这里为了避免页面变化，故使用相对位置定位：作品标题父级右侧第一个元素的input子元素
        await asyncio.sleep(1)
        print("  [-] 正在填充标题和话题...")
        title_container = page.get_by_text('作品标题').locator("..").locator("xpath=following-sibling::div[1]").locator("input")
        if await title_container.count():
            await title_container.fill(self.title[:30])
        else:
            titlecontainer = page.locator(".notranslate")
            await titlecontainer.click()
            print("clear existing title")
            await page.keyboard.press("Backspace")
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.press("Delete")
            print("filling new  title")
            await page.keyboard.type(self.title)
            await page.keyboard.press("Enter")
        css_selector = ".zone-container"
        for index, tag in enumerate(self.tags, start=1):
            print("正在添加第%s个话题" % index)
            await page.type(css_selector, "#" + tag)
            await page.press(css_selector, "Space")

        while True:
            # 判断重新上传按钮是否存在，如果不存在，代表视频正在上传，则等待
            try:
                #  新版：定位重新上传
                number = await page.locator('div label+div:has-text("重新上传")').count()
                if number > 0:
                    print("  [-]视频上传完毕")
                    break
                else:
                    print("  [-] 正在上传视频中...")
                    await asyncio.sleep(2)

                    if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                        print("  [-] 发现上传出错了...")
                        await self.handle_upload_error(page)
            except:
                print("  [-] 正在上传视频中...")
                await asyncio.sleep(2)

        # 更换可见元素
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await asyncio.sleep(1)
        print("clear existing location")
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        await page.keyboard.type(self.location)
        await asyncio.sleep(1)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

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

        # 判断视频是否发布成功
        while True:
            # 判断视频是否发布成功
            try:
                publish_button = page.get_by_role('button', name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url("https://creator.douyin.com/creator-micro/content/manage",
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


