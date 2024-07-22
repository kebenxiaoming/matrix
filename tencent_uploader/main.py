# -*- coding: utf-8 -*-
from datetime import datetime
from playwright.async_api import Playwright, async_playwright
import os
import asyncio
import redis

from conf import REDIS_CONF
from utils.files_times import get_absolute_path


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
        browser = await playwright.chromium.launch(headless=True)
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

def cache_data(key:str,value:str,timeout=60)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.set(key, value)
    redis_client.expire(key, timeout)

async def save_storage_state(account_file_path: str,account_id:str,queue_id:str):
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
            # 加载首页
            await page.goto("https://channels.weixin.qq.com/platform/login-for-iframe?dark_mode=true&host_type=1")
            await page.locator('.qrcode').click()
            # 加载扫码页
            img_element = await page.locator('img.qrcode').get_attribute("src")
            # 将id和base64的关系存到redis
            cache_data(f"tencent_login_ewm_{queue_id}",img_element)
            # 等待过程换成循环，然后同时检测状态
            num = 1
            success_img_div = page.locator(".mask").first
            success_show_class = await success_img_div.get_attribute("class")
            while True:
                await asyncio.sleep(3)
                # 判断是否有已扫码显示，如果有跳出循环
                success_show_class = await success_img_div.get_attribute("class")
                if "show" in success_show_class:
                    # 保存记录一下说明已经扫码
                    cache_data(f"tencent_login_scan_{queue_id}",1,6)
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
            # 保存cookie长度不大于30不保存
            if len(cookies) > 0:
                # 查找用户信息
                page = await context.new_page()
                await page.goto("https://channels.weixin.qq.com/platform")
                await page.wait_for_url("https://channels.weixin.qq.com/platform")
                third_id = await page.locator("span.finder-uniq-id").nth(0).inner_text()
                user_info = {
                    'account_id':third_id,
                    'username':await page.locator("h2.finder-nickname").nth(0).inner_text(),
                    'avatar':await page.locator("img.avatar").nth(0).get_attribute("src")
                }
                # 保存cookie
                account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
                await context.storage_state(path=account_file)
                # 保存登录状态
                cache_data(f"tencent_login_status_{account_id}",1,60)
                # 保存抖音账号的登录状态，时间一个周
                cache_data(f"tencent_login_status_third_{account_id}_{third_id}",1,86400)
            # 关闭浏览器
            await context.close()
            await browser.close()
            await playwright.stop()
            return user_info
    except:
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
        # 使用 firefox (这里使用系统内浏览器，用chromium 会造成h264错误
        browser = await playwright.chromium.launch(headless=False,channel="chrome")
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")
        
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://channels.weixin.qq.com/platform/post/create")
        print('[+]正在上传-------{}'.format(self.file_path))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        await page.wait_for_url("https://channels.weixin.qq.com/platform/post/create")
        # await page.wait_for_selector('input[type="file"]', timeout=10000)
        # file_input = page.locator('input[type="file"]')
        # await page.screenshot(path="/home/www/matrix/videos/0.png")
        # await file_input.set_input_files(self.file_path)
        # await page.screenshot(path="/home/www/matrix/videos/1.png")
        upload_div_loc = page.locator("div.upload-content")
        # await upload_div_loc.wait_for()
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
        while True:
            try:
                publish_buttion = page.locator('div.form-btns button:has-text("发表")')
                if await publish_buttion.count():
                    await publish_buttion.click()
                await page.wait_for_url("https://channels.weixin.qq.com/platform/post/list", timeout=10000)
                print("  [-]视频发布成功")
                break
            except Exception as e:
                current_url = page.url
                if "https://channels.weixin.qq.com/platform/post/list" in current_url:
                    print("  [-]视频发布成功")
                    break
                else:
                    print(f"  [-] Exception: {e}")
                    print("  [-] 视频正在发布中...")
                    await page.screenshot(full_page=True)
                    await asyncio.sleep(0.5)

    async def detact_upload_status(self, page):
        while True:
            # 匹配删除按钮，代表视频上传完毕，如果不存在，代表视频正在上传，则等待
            try:
                # 匹配删除按钮，代表视频上传完毕
                button_info = await page.get_by_role("button", name="发表").get_attribute(
                        'class')
                if "weui-desktop-btn_disabled" not in button_info:
                    print("  [-]视频上传完毕")
                    # 上传完毕修改封面图
                    # 等待处理完预览图
                    await asyncio.sleep(2)
                    preview_button_info = await page.locator('div.finder-tag-wrap.btn:has-text("更换封面")').get_attribute(
                                    'class')
                    if "disabled" not in preview_button_info:
                        await page.locator('div.finder-tag-wrap.btn:has-text("更换封面")').click()
                        await page.locator('div.single-cover-uploader-wrap > div.wrap').hover()
                        if await page.locator(".del-wrap > .svg-icon").count():
                            await page.locator(".del-wrap > .svg-icon").click()
                        preview_upload_div_loc = page.locator("div.single-cover-uploader-wrap > div.wrap")
                        #await upload_div_loc.wait_for()
                        async with page.expect_file_chooser() as fc_info:
                            await preview_upload_div_loc.click()
                        preview_file_chooser = await fc_info.value
                        await preview_file_chooser.set_files(self.video_preview)
                        #await page.locator('div.single-cover-uploader-wrap > input').set_input_files(self.video_preview)
                        await asyncio.sleep(2)
                        await page.get_by_role("button", name="确定").click()
                        await asyncio.sleep(1)
                        await page.get_by_role("button", name="确认").click()
                        break
                else:
                    print("  [-] 正在上传视频中...")
                    await asyncio.sleep(2)
                    # 出错了视频出错
                    if await page.locator('div.status-msg.error').count() and await page.locator(
                            'div.media-status-content div.tag-inner:has-text("删除")').count():
                        print("  [-] 发现上传出错了...")
                        await self.handle_upload_error(page)
            except:
                print("  [-] 正在上传视频中...")
                await asyncio.sleep(2)

    async def add_title_tags(self, page):
        await page.locator("div.input-editor").click()
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
