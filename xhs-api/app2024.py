import asyncio
import traceback  
from pathlib import Path
from flask import Flask, request
from playwright.async_api import async_playwright

# 单次请求无头调用playwright的实现，目前app.py是先开启playwright再接收请求
# 这里的实现是请求一次无头开启一次playwright，默认不开启

app = Flask(__name__)

global_a1 = "187d2defea8dz1fgwydnci40kw265ikh9fsxn66qs50000726043"

BASE_DIR = Path(__file__).parent.resolve()
stealth_js_path = Path(BASE_DIR / "js"/ "stealth.min.js")

async def playwright_main(uri, data, a1, web_session):
    try:
        # 先查询是否存在a1的cache，存在直接返回
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            browser_context = await browser.new_context()
            await browser_context.add_init_script(path=stealth_js_path)
            context_page = await browser_context.new_page()
            await context_page.goto("https://www.xiaohongshu.com")
            # https://creator.xiaohongshu.com
            # context_page.goto("https://creator.xiaohongshu.com")
            # await context_page.wait_for_url("https://www.xiaohongshu.com/explore",timeout = 5000)
            await asyncio.sleep(1)
            await context_page.reload()
            await asyncio.sleep(1)
            cookies = await browser_context.cookies()
            for cookie in cookies:
                if cookie["name"] == "a1":
                    global_a1 = cookie["value"]
            if a1 != global_a1:
                await browser_context.add_cookies([
                    {'name': 'a1', 'value': a1, 'domain': ".xiaohongshu.com", 'path': "/"}
                ])
                await context_page.reload()
                await asyncio.sleep(0.5)
                global_a1 = a1
            encrypt_params = await context_page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
            # 关闭浏览器上下文和浏览器实例
            await browser_context.close()
            await browser.close()
            await playwright.stop()
            result = {
                "x-s": encrypt_params["X-s"],
                "x-t": str(encrypt_params["X-t"])
            }
            return result
    except:
        traceback.print_exc()
        return {
            "x-s": "",
            "x-t": ""
        }

@app.route("/sign", methods=["POST"])
def hello_world():
    json = request.json
    uri = json["uri"]
    data = json["data"]
    a1 = json["a1"]
    web_session = json["web_session"]
    result = asyncio.run(playwright_main(uri, data, a1, web_session),debug=False) 
    return result


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5005)
