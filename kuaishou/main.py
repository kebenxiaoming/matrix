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


def create_batch_upload(video_list, account_list, max_concurrent=1, delay=5):
    """
    便捷函数：创建批量上传任务
    
    Args:
        video_list: 视频列表，每个元素是字典，包含：
            {
                'title': '视频标题',
                'file_path': '视频文件路径',
                'video_preview': '预览图路径',
                'tags': ['标签1', '标签2'],  # 可选
                'publish_date': datetime对象或0,  # 可选
                'location': '位置'  # 可选
            }
        account_list: 账号列表，每个元素是账号cookie文件路径字符串
        max_concurrent: 最大并发数（默认1，顺序上传）
        delay: 每个上传任务之间的延迟（秒）
    
    Returns:
        KuaiShouBatchUpload 实例
    
    Example:
        # 视频矩阵（一行）
        videos = [
            {'title': '视频1', 'file_path': 'video1.mp4', 'video_preview': 'preview1.jpg'},
            {'title': '视频2', 'file_path': 'video2.mp4', 'video_preview': 'preview2.jpg'},
        ]
        
        # 账号矩阵（一列）
        accounts = [
            'account1.json',
            'account2.json',
            'account3.json',
        ]
        
        # 创建批量上传器（矩阵相乘：2个视频 × 3个账号 = 6个任务）
        batch = create_batch_upload(videos, accounts, max_concurrent=1)
        await batch.main()
    """
    return KuaiShouBatchUpload(
        video_matrix=video_list,
        account_matrix=account_list,
        max_concurrent=max_concurrent,
        delay_between_uploads=delay
    )


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


class KuaiShouBatchUpload(object):
    """
    批量上传类：实现视频矩阵 × 账号矩阵的批量上传
    视频矩阵：一行，每个元素是一个视频信息
    账号矩阵：一列，每个元素是一个账号文件路径
    矩阵相乘：生成所有视频×账号的组合任务
    """
    def __init__(self, video_matrix, account_matrix, max_concurrent=1, delay_between_uploads=5):
        """
        初始化批量上传器
        
        Args:
            video_matrix: 视频矩阵（列表），每个元素是字典，包含：
                {
                    'title': '视频标题',
                    'file_path': '视频文件路径',
                    'video_preview': '预览图路径',
                    'tags': ['标签1', '标签2'],
                    'publish_date': datetime对象或0,
                    'location': '位置' (可选)
                }
            account_matrix: 账号矩阵（列表），每个元素是账号cookie文件路径字符串
            max_concurrent: 最大并发数（默认1，顺序上传）
            delay_between_uploads: 每个上传任务之间的延迟（秒）
        """
        self.video_matrix = video_matrix  # 视频矩阵（行）
        self.account_matrix = account_matrix  # 账号矩阵（列）
        self.max_concurrent = max_concurrent
        self.delay_between_uploads = delay_between_uploads
        self.local_executable_path = ""  # change me
        self.results = []  # 存储上传结果
        self.total_tasks = len(video_matrix) * len(account_matrix)
        
    def generate_task_matrix(self):
        """
        生成任务矩阵：视频矩阵 × 账号矩阵
        返回所有任务组合的列表
        """
        tasks = []
        for video_idx, video_info in enumerate(self.video_matrix):
            for account_idx, account_file in enumerate(self.account_matrix):
                task = {
                    'task_id': f"V{video_idx+1}_A{account_idx+1}",
                    'video_info': video_info,
                    'account_file': account_file,
                    'video_index': video_idx + 1,
                    'account_index': account_idx + 1,
                    'total_videos': len(self.video_matrix),
                    'total_accounts': len(self.account_matrix)
                }
                tasks.append(task)
        return tasks
    
    async def upload_single_task(self, task, semaphore=None):
        """
        上传单个任务（视频×账号）
        """
        if semaphore:
            async with semaphore:
                return await self._execute_upload(task)
        else:
            return await self._execute_upload(task)
    
    async def _execute_upload(self, task):
        """
        执行单个上传任务
        """
        task_id = task['task_id']
        video_info = task['video_info']
        account_file = task['account_file']
        
        print(f"\n{'='*60}")
        print(f"[任务 {task_id}] 开始上传")
        print(f"  视频: {video_info.get('title', '未知')} ({task['video_index']}/{task['total_videos']})")
        print(f"  账号: {account_file} ({task['account_index']}/{task['total_accounts']})")
        print(f"{'='*60}")
        
        result = {
            'task_id': task_id,
            'video_title': video_info.get('title', ''),
            'account_file': account_file,
            'status': 'pending',
            'error': None,
            'start_time': datetime.now(),
            'end_time': None
        }
        
        try:
            # 创建上传实例
            uploader = KuaiShouVideo(
                title=video_info.get('title', ''),
                file_path=video_info.get('file_path', ''),
                video_preview=video_info.get('video_preview', ''),
                tags=video_info.get('tags', []),
                publish_date=video_info.get('publish_date', 0),
                account_file=account_file,
                location=video_info.get('location', '重庆市')
            )
            
            if self.local_executable_path:
                uploader.local_executable_path = self.local_executable_path
            
            # 执行上传
            async with async_playwright() as playwright:
                await uploader.upload(playwright)
            
            result['status'] = 'success'
            result['end_time'] = datetime.now()
            duration = (result['end_time'] - result['start_time']).total_seconds()
            print(f"\n[任务 {task_id}] ✓ 上传成功！耗时: {duration:.1f}秒")
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            result['end_time'] = datetime.now()
            duration = (result['end_time'] - result['start_time']).total_seconds()
            print(f"\n[任务 {task_id}] ✗ 上传失败！耗时: {duration:.1f}秒")
            print(f"  错误信息: {str(e)}")
            traceback.print_exc()
        
        return result
    
    async def upload_all(self):
        """
        执行所有上传任务
        支持并发或顺序执行
        """
        tasks = self.generate_task_matrix()
        total = len(tasks)
        
        print(f"\n{'#'*60}")
        print(f"批量上传任务开始")
        print(f"  视频数量: {len(self.video_matrix)}")
        print(f"  账号数量: {len(self.account_matrix)}")
        print(f"  总任务数: {total}")
        print(f"  并发数: {self.max_concurrent}")
        print(f"{'#'*60}\n")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent) if self.max_concurrent > 1 else None
        
        # 执行所有任务
        if self.max_concurrent > 1:
            # 并发执行
            upload_tasks = [self.upload_single_task(task, semaphore) for task in tasks]
            results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # 处理异常结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.results.append({
                        'task_id': tasks[i]['task_id'],
                        'status': 'failed',
                        'error': str(result)
                    })
                else:
                    self.results.append(result)
                
                # 任务间延迟
                if i < len(results) - 1:
                    await asyncio.sleep(self.delay_between_uploads)
        else:
            # 顺序执行
            for i, task in enumerate(tasks):
                result = await self.upload_single_task(task)
                self.results.append(result)
                
                # 任务间延迟
                if i < len(tasks) - 1:
                    await asyncio.sleep(self.delay_between_uploads)
        
        # 打印统计信息
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """
        打印上传结果统计
        """
        total = len(self.results)
        success = sum(1 for r in self.results if r.get('status') == 'success')
        failed = sum(1 for r in self.results if r.get('status') == 'failed')
        
        print(f"\n{'#'*60}")
        print(f"批量上传完成统计")
        print(f"{'#'*60}")
        print(f"  总任务数: {total}")
        print(f"  成功: {success} ({success/total*100:.1f}%)" if total > 0 else "  成功: 0")
        print(f"  失败: {failed} ({failed/total*100:.1f}%)" if total > 0 else "  失败: 0")
        print(f"{'#'*60}\n")
        
        # 打印失败的任务
        if failed > 0:
            print("失败的任务列表:")
            for result in self.results:
                if result.get('status') == 'failed':
                    print(f"  - {result.get('task_id')}: {result.get('error', '未知错误')}")
            print()
    
    def get_results(self):
        """
        获取上传结果
        """
        return self.results
    
    async def main(self):
        """
        主入口方法
        """
        return await self.upload_all()


class KuaiShouLive(object):
    def __init__(self, title, video_path, cover_image, account_file, location="重庆市"):
        self.title = title  # 直播标题
        self.video_path = video_path  # 用于直播的视频文件路径
        self.cover_image = cover_image  # 直播封面图
        self.account_file = account_file  # 账号cookie文件
        self.local_executable_path = ""  # change me
        self.location = location

    async def create_video_player_page(self, context, video_path):
        """
        创建一个新页面来播放视频，用于屏幕共享
        """
        import os
        # 将视频路径转换为绝对路径
        if not os.path.isabs(video_path):
            video_path = os.path.abspath(video_path)
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 创建新页面
        video_page = await context.new_page()
        
        # 创建 HTML 页面来播放视频
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>视频播放器 - 直播源</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                body {
                    background: #000;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    width: 100vw;
                    overflow: hidden;
                }
                video {
                    max-width: 100%;
                    max-height: 100%;
                    width: auto;
                    height: auto;
                    object-fit: contain;
                }
            </style>
        </head>
        <body>
            <video id="videoPlayer" autoplay loop muted playsinline></video>
            <script>
                const video = document.getElementById('videoPlayer');
                
                // 等待文件被设置
                function setupVideo() {
                    const input = document.querySelector('input[type="file"]');
                    if (input && input.files && input.files.length > 0) {
                        const file = input.files[0];
                        const url = URL.createObjectURL(file);
                        video.src = url;
                        video.play().catch(err => {
                            console.error('播放失败:', err);
                        });
                    } else {
                        // 如果文件还没设置，稍后再试
                        setTimeout(setupVideo, 100);
                    }
                }
                
                // 监听视频加载
                video.addEventListener('loadedmetadata', () => {
                    console.log('视频元数据已加载，尺寸:', video.videoWidth, 'x', video.videoHeight);
                });
                
                video.addEventListener('play', () => {
                    console.log('视频开始播放');
                });
                
                video.addEventListener('ended', () => {
                    console.log('视频播放结束，重新开始');
                    video.currentTime = 0;
                    video.play();
                });
                
                // 开始设置
                setupVideo();
            </script>
        </body>
        </html>
        """
        
        # 设置页面内容
        await video_page.set_content(html_content)
        
        # 创建文件输入并设置视频文件
        await video_page.evaluate("""
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'video/*';
            input.style.display = 'none';
            input.id = 'video-file-input';
            document.body.appendChild(input);
        """)
        
        # 使用 Playwright 设置文件
        file_input = video_page.locator('#video-file-input')
        await file_input.set_input_files(video_path)
        
        # 等待文件设置完成
        await video_page.wait_for_timeout(500)
        
        # 触发文件加载
        await video_page.evaluate("""
            const input = document.getElementById('video-file-input');
            if (input.files && input.files.length > 0) {
                const file = input.files[0];
                const video = document.getElementById('videoPlayer');
                const url = URL.createObjectURL(file);
                video.src = url;
                video.play();
            }
        """)
        
        # 等待视频开始播放
        try:
            await video_page.wait_for_function(
                "document.getElementById('videoPlayer').readyState >= 2",
                timeout=10000
            )
            print("  [-] 视频已加载并开始播放")
        except:
            print("  [-] 视频加载超时，但页面已创建")
        
        return video_page

    async def start_live(self, playwright: Playwright) -> None:
        """
        开始直播
        """
        # 使用 Chromium 浏览器启动一个浏览器实例
        if self.local_executable_path:
            browser = await playwright.chromium.launch(headless=False, executable_path=self.local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=False)
        
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")

        # 创建一个新的页面
        page = await context.new_page()
        
        # 访问快手的直播页面
        print('[+] 正在打开直播页面...')
        await page.goto("https://cp.kuaishou.com/live/create")
        
        # 等待页面加载
        await asyncio.sleep(2)
        
        video_page = None
        try:
            # 检查是否需要等待页面完全加载
            print('[-] 正在等待直播页面加载...')
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # 设置直播标题
            print("  [-] 正在设置直播标题...")
            title_input = page.locator('input[placeholder*="标题"], input[placeholder*="直播标题"], textarea[placeholder*="标题"]').first
            if await title_input.count() > 0:
                await title_input.click()
                await title_input.fill(self.title)
                await asyncio.sleep(1)
            
            # 上传封面图
            if self.cover_image:
                print("  [-] 正在上传直播封面...")
                try:
                    # 查找上传封面的按钮
                    cover_buttons = [
                        page.get_by_role("button", name="上传封面"),
                        page.get_by_text("上传封面"),
                        page.locator('button:has-text("上传封面")'),
                        page.locator('div:has-text("上传封面")'),
                    ]
                    
                    for cover_button in cover_buttons:
                        if await cover_button.count() > 0:
                            async with page.expect_file_chooser() as fc_info:
                                await cover_button.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(self.cover_image)
                            await asyncio.sleep(2)
                            break
                except Exception as e:
                    print(f"  [-] 上传封面失败: {e}")
            
            # 创建视频播放页面（用于屏幕共享）
            print("  [-] 正在创建视频播放页面...")
            try:
                video_page = await self.create_video_player_page(context, self.video_path)
                # 将视频页面最大化以便共享
                await video_page.set_viewport_size({"width": 1920, "height": 1080})
                await asyncio.sleep(1)
            except Exception as e:
                print(f"  [-] 创建视频播放页面失败: {e}")
                traceback.print_exc()
            
            # 选择直播源（屏幕共享）
            print("  [-] 正在选择直播源...")
            try:
                # 查找选择直播源的按钮
                source_selectors = [
                    page.get_by_text("屏幕共享"),
                    page.get_by_text("选择直播源"),
                    page.get_by_text("摄像头"),
                    page.locator('button:has-text("屏幕")'),
                    page.locator('div:has-text("屏幕")'),
                ]
                
                source_selected = False
                for selector in source_selectors:
                    if await selector.count() > 0:
                        await selector.click()
                        await asyncio.sleep(2)
                        source_selected = True
                        print("  [-] 已选择屏幕共享")
                        break
                
                if not source_selected:
                    print("  [-] 未找到直播源选择按钮，可能需要手动选择")
                    print("  [-] 提示：请手动选择'屏幕共享'，然后选择视频播放窗口")
                
            except Exception as e:
                print(f"  [-] 选择直播源时出错: {e}")
                print("  [-] 提示：请手动选择'屏幕共享'作为直播源")
            
            # 开始直播
            print("  [-] 正在开始直播...")
            start_buttons = [
                page.get_by_role("button", name="开始直播"),
                page.get_by_text("开始直播"),
                page.locator('button:has-text("开始直播")'),
            ]
            
            live_started = False
            for start_button in start_buttons:
                if await start_button.count() > 0:
                    await start_button.click()
                    live_started = True
                    print("  [-] 直播已开始！")
                    break
            
            if not live_started:
                print("  [-] 未找到开始直播按钮，可能需要手动操作")
            
            # 保持直播运行
            print("  [-] 直播进行中，按 Ctrl+C 停止...")
            try:
                # 持续检查直播状态
                while True:
                    await asyncio.sleep(5)
                    # 检查是否还在直播页面
                    current_url = page.url
                    if "live" not in current_url.lower():
                        print("  [-] 检测到已离开直播页面")
                        break
            except KeyboardInterrupt:
                print("  [-] 收到停止信号，正在结束直播...")
            
            # 结束直播
            print("  [-] 正在结束直播...")
            stop_buttons = [
                page.get_by_role("button", name="结束直播"),
                page.get_by_text("结束直播"),
                page.locator('button:has-text("结束直播")'),
            ]
            
            for stop_button in stop_buttons:
                if await stop_button.count() > 0:
                    await stop_button.click()
                    await asyncio.sleep(2)
                    print("  [-] 直播已结束")
                    break
            
        except Exception as e:
            print(f"  [-] 直播过程中出错: {e}")
            traceback.print_exc()
        finally:
            # 确保关闭视频播放页面
            if video_page:
                try:
                    await video_page.close()
                    print("  [-] 视频播放页面已关闭")
                except:
                    pass
        
        # 保存cookie
        await context.storage_state(path=self.account_file)
        print('  [-] cookie更新完毕！')
        await asyncio.sleep(2)
        
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()
        await playwright.stop()

    async def main(self):
        async with async_playwright() as playwright:
            await self.start_live(playwright)


# ============================================================================
# 使用示例：批量上传（视频矩阵 × 账号矩阵）
# ============================================================================
"""
示例代码：

import asyncio
from datetime import datetime

async def batch_upload_example():
    # 视频矩阵（一行）：定义要上传的视频列表
    video_matrix = [
        {
            'title': '视频标题1',
            'file_path': '/path/to/video1.mp4',
            'video_preview': '/path/to/preview1.jpg',
            'tags': ['标签1', '标签2'],
            'publish_date': 0,  # 0表示立即发布，或使用datetime对象定时发布
            'location': '重庆市'
        },
        {
            'title': '视频标题2',
            'file_path': '/path/to/video2.mp4',
            'video_preview': '/path/to/preview2.jpg',
            'tags': [],
            'publish_date': 0,
            'location': '重庆市'
        },
    ]
    
    # 账号矩阵（一列）：定义要使用的账号列表
    account_matrix = [
        '/path/to/account1.json',
        '/path/to/account2.json',
        '/path/to/account3.json',
    ]
    
    # 创建批量上传器
    # 矩阵相乘：2个视频 × 3个账号 = 6个上传任务
    batch_uploader = KuaiShouBatchUpload(
        video_matrix=video_matrix,      # 视频矩阵（行）
        account_matrix=account_matrix,   # 账号矩阵（列）
        max_concurrent=1,                # 并发数：1=顺序上传，>1=并发上传
        delay_between_uploads=5          # 每个任务之间的延迟（秒）
    )
    
    # 执行批量上传
    results = await batch_uploader.upload_all()
    
    # 查看结果
    for result in results:
        print(f"任务 {result['task_id']}: {result['status']}")

# 运行示例
# asyncio.run(batch_upload_example())

# 或者使用便捷函数：
# batch = create_batch_upload(video_matrix, account_matrix, max_concurrent=1)
# await batch.main()
"""
