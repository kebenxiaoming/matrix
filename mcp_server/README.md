# 视频矩阵分发 MCP Server

把「把本地视频发布到抖音 / 视频号 / 小红书 / 快手」的能力封装成 MCP 工具，
任何支持 Model Context Protocol 的 AI 客户端都可以直接调用。

- 复用桌面客户端的同一套发布内核（`desktop/core/publisher.py`），**不含 PySide6**
- 全局串行队列：四个平台共用同一台机器和浏览器，并发只会互相踩
- 所有返回都是结构化 JSON，失败带可读错误码，AI 能自己纠正参数
- 不暴露任何 cookie / 登录凭据

---

## 1. 前置条件

| 项目 | 要求 | 说明 |
|---|---|---|
| Python | ≥ 3.10（推荐 3.13） | `mcp` SDK 2.x 的要求 |
| Google Chrome | 必须安装 | 视频号、小红书依赖 h264 编码，内置 Chromium 传不动 |
| 账号 | 已在桌面客户端扫码登录过 | **扫码是人在环，AI 无法代做** |
| 系统 | Windows / macOS / Linux | 三者都支持，路径自动适配 |

---

## 2. 安装

在项目根目录执行（`D:\wwwroot\matrix\matrix`）：

```bash
# 建独立虚拟环境（不想污染桌面客户端的 .venv-desktop）
python -m venv .venv-mcp

# Windows
.venv-mcp\Scripts\activate
# macOS / Linux
source .venv-mcp/bin/activate

pip install -r mcp_server/requirements.txt
python -m playwright install chromium
```

> 已经装了 `.venv-desktop` 的话，直接用也行，只补一个 `pip install "mcp>=2.3"` 即可。
> 桌面客户端的打包不受影响——PyInstaller 只收集被 `desktop/main.py` 引用到的模块。

验证安装：

```bash
python -m mcp_server
```

正常表现：进程挂住不退出，stderr 打印 `[matrix-mcp] 已启动，等待客户端调用…`。
这是 stdio 模式在等客户端发 `initialize`，不是卡死。`Ctrl+C` 退出。

---

## 3. 数据目录（最容易踩的坑）

MCP 和桌面客户端必须是**同一个数据库**，否则看不到已登录的账号。

自动探测顺序：

1. 环境变量 `MATRIX_DATA_DIR`（最高优先级）
2. `dist/视频矩阵分发/data`（桌面客户端绿色版的数据目录）
3. `data/`（项目根，开发态）

调 `matrix_health` 会返回实际使用的 `data_dir`，对不上就手动指定：

```
MATRIX_DATA_DIR=D:\wwwroot\matrix\matrix\dist\视频矩阵分发\data
```

> macOS 上打包版的数据在 `~/Library/Application Support/MatrixPublisher`，
> 直接设 `MATRIX_DATA_DIR` 指过去。

---

## 4. 接入 AI 客户端

### Claude Desktop

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "matrix-publisher": {
      "command": "D:\\wwwroot\\matrix\\matrix\\.venv-mcp\\Scripts\\python.exe",
      "args": ["-m", "mcp_server"],
      "cwd": "D:\\wwwroot\\matrix\\matrix",
      "env": {
        "PYTHONPATH": "D:\\wwwroot\\matrix\\matrix",
        "MATRIX_ALLOWED_DIRS": "D:\\videos"
      }
    }
  }
}
```

### WorkBuddy

写入 `~/.workbuddy/mcp.json`，结构同上（顶层 `mcpServers`）：

```json
{
  "mcpServers": {
    "matrix-publisher": {
      "command": "D:/wwwroot/matrix/matrix/.venv-mcp/Scripts/python.exe",
      "args": ["-m", "mcp_server"],
      "cwd": "D:/wwwroot/matrix/matrix",
      "env": { "PYTHONPATH": "D:/wwwroot/matrix/matrix" }
    }
  }
}
```

### Cursor

项目内 `.cursor/mcp.json`，结构同上。

### DeepSeek Harness（DSH）

DSH 通过 `@deepseek-ai/dsh-mcp-client` 桥接外部 MCP server，把上面的
`command` / `args` / `cwd` / `env` 原样填进去即可。注意两点 DSH 的硬限制：

- **只桥接 tools**，resources 和 prompts 不支持（本 server 只提供 tools，正好）
- MCP server 默认不启用，需要在配置层显式打开
- 工具在 DSH 里显示为 `mcp__matrix-publisher__matrix_publish` 这类名字

DSH 还在开发者预览期，配置层的字段随版本变化，以 `dsh --profile web --dump-config`
打印出来的实际配置树为准。**建议先在 Claude Desktop / WorkBuddy 里跑通，再迁到 DSH**，
这样可以排除 Python 侧的问题，只排查 DSH 的配置。

---

## 5. 工具清单

| 工具 | 作用 | 典型耗时 |
|---|---|---|
| `matrix_list_platforms` | 列出平台 key / id / 中文别名 | < 100ms |
| `matrix_list_accounts` | 列出账号与登录状态（不含凭据） | < 100ms |
| `matrix_check_login` | 校验登录是否有效 | 抖音 ~9s / 视频号 ~5s / 快手 ~8s / 小红书 < 1s |
| `matrix_login` | 扫码登录或续期，**会弹出浏览器窗口** | 取决于用户扫码，最长 300s |
| `matrix_publish` | 发布单条，阻塞到出结果 | 20–40s |
| `matrix_publish_batch` | 批量入队，立即返回 task_id | < 200ms |
| `matrix_task_status` | 按 task_id / batch_id 查进度 | < 100ms |
| `matrix_health` | 自检环境（浏览器、数据目录、队列） | 1–2s |

平台参数统一用 key：`douyin`、`tencent`、`xhs`、`ks`，也接受中文名和数字 id。

### 一次典型调用的参数

```json
{
  "platform": "douyin",
  "account_id": 1,
  "video_path": "D:\\videos\\demo.mp4",
  "title": "重庆小面探店",
  "tags": ["重庆美食", "探店"],
  "cover_path": null,
  "description": "",
  "publish_at": "2026-11-07 09:30",
  "dry_run": true
}
```

`dry_run=true` 只校验参数、路径、登录，不会真的发布。**建议 AI 每次都先跑一次 dry_run。**

### 登录：二维码不需要 AI 传输

`matrix_login` 不是一个"让 AI 假装完成登录"的工具。它的做法是**在本机弹出浏览器**，
二维码就在窗口里，用户拿手机扫一下即可：

| 平台 | 二维码在哪 | 说明 |
|---|---|---|
| 抖音 / 视频号 / 快手 | 弹出的 Chrome 窗口 | 登录页本身就是扫码页 |
| 小红书 | 本地 PNG 图片 | 没有浏览器窗口，会自动用系统看图器打开 |

```json
{ "platform": "tencent", "account_id": 7 }
```

新建账号时只传 `platform`，工具会先建一条占位记录；登录失败或超时会自动删掉，
不留垃圾数据。同一第三方账号已存在时会合并到原记录，返回的 `account_id`
是合并后真正存活的那个。

**这一步必须有人参与**，AI 只能把窗口调出来、等结果，不能代替扫码。
扫码期间最长等 300 秒，别重复调用。

---

## 6. 错误码

| code | 含义 | 处理方式 |
|---|---|---|
| `NEED_HUMAN_LOGIN` | 账号没登录或已失效 | 调 `matrix_login` 让用户扫码续期 |
| `LOGIN_FAILED` | 扫码没完成 / 窗口被关 / 超时 | 重试 `matrix_login`；看 `error` 原文 |
| `BUSY` | 发布队列正在跑任务，登录没能拿到执行权 | 等任务结束再登录 |
| `ACCOUNT_NOT_FOUND` | account_id 不存在 | 先调 `matrix_list_accounts` |
| `PLATFORM_MISMATCH` | 账号和 platform 对不上 | 用账号真实的平台 |
| `UNSUPPORTED_PLATFORM` | 平台名不认识 | 只用 `douyin/tencent/xhs/ks` |
| `PATH_NOT_ALLOWED` | 视频不在允许目录 | 设 `MATRIX_ALLOWED_DIRS`，或把视频放进去 |
| `BAD_ARGUMENT` | 路径不存在 / 扩展名不支持 / 时间格式错 | 按 error 文案改参数 |
| `TIMEOUT` | 等待超时，任务仍在后台执行 | **不要重复提交**，用 `matrix_task_status` 查 |
| `PUBLISH_FAILED` | 平台侧失败 | 看 `error` 原文，必要时看 `data/logs/mcp.log` |
| `TASK_NOT_FOUND` | 任务 id 不存在 | 检查 task_id |
| `CREATE_FAILED` | 一条任务都没建成 | 看 `rejected` 里的原因 |

---

## 7. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `MATRIX_DATA_DIR` | 自动探测 | 数据目录，必须与客户端一致 |
| `MATRIX_ALLOWED_DIRS` | 数据目录 | 允许读取视频的目录，多个用 `;`（Windows）/ `:`（macOS）分隔 |
| `MATRIX_PUBLISH_TIMEOUT` | `300` | 单次 `matrix_publish` 最长等待秒数 |
| `MATRIX_TASK_GAP` | `15` | 队列中两个任务之间的间隔秒数，防风控 |
| `MATRIX_HEADLESS` | `1` | 设为 `0` 可看到浏览器窗口，排查问题时用 |
| `MATRIX_TENCENT_CHANNEL` | 自动 | 视频号指定 Chrome 路径 |

---

## 8. 常见问题

**Q：`matrix_list_accounts` 返回 0，但客户端里明明有账号**

数据目录不一致。调 `matrix_health` 看 `data_dir`，再用 `MATRIX_DATA_DIR` 指到客户端实际用的目录。

**Q：视频号 / 小红书一直在发布中然后失败**

大概率没装系统 Chrome，回退到缺 h264 的内置 Chromium。`matrix_health` 的
`chrome_ok` 为 `false` 就是这个原因。装完 Chrome 重启 MCP 进程。

**Q：`NEED_HUMAN_LOGIN` 反复出现**

cookie 真的过期了，直接调 `matrix_login` 重新扫码即可，不用专门打开桌面客户端。

`matrix_check_login` 是**真实访问验证**，不是只看文件在不在，所以会有耗时：
抖音 ~9s、视频号 ~5s、快手 ~8s，小红书是一次本地的字符串检查（<1s）。
视频号以前只判断 cookie 文件非空，导致过期账号要先空等 60 多秒、最后报
「找不到上传框」，现在会直接返回 `NEED_HUMAN_LOGIN`。

**Q：调了 `matrix_login`，但没看到二维码窗口**

MCP server 是后台进程，它拉起的 Chrome 会被系统以「最小化 + 坐标在屏幕外」创建
（实测窗口 rect 是 `-25600,-25600`）。`utils/window_focus.py` 会在登录开始后
40 秒内每秒扫一次，把浏览器窗口恢复到屏幕中央并置前。

如果仍然看不到：检查是不是在远程桌面/无显示器环境里跑，那种环境没有可见桌面，
只能退回「用桌面客户端扫码 + MCP 只负责发布」的老办法。

**Q：工具一调用就报 `Failed to parse JSONRPC message` / `Connection closed`**

stdout 被非协议内容污染了。MCP 走 stdio，stdout 是 JSONRPC 专用管线，任何一行普通
文本都会让客户端解析失败。四个 uploader 里有 60 多处 `print()`，桌面端无所谓，
在 MCP 下必须改道。

`stdio_guard.py` 在服务启动前把真正的协议管线 dup 到私有 fd，再把 fd 1 整体指向
stderr，因此 `print()`、`os.write(1, ...)`、子进程输出都不会再碰到管线。
MCP SDK 自带的 stdio 分流在 Windows 上只改 OS 句柄、不改 CRT fd，对 Python 的
`sys.stdout` 无效——这是实测踩出来的，别删这个文件。

**Q：提示「已有另一个 MCP 实例在运行」**

`.mcp.lock` 被占用。关掉其他客户端里的 `matrix-publisher`，或结束残留 Python 进程。
锁文件在数据目录下，进程正常退出会自动释放。

**Q：能不能同时开桌面客户端的队列和 MCP？**

不建议。两边都会开 Chrome、都会消费任务，同一账号并发发布容易被风控。
**用 MCP 时把客户端的队列停掉**，客户端只用来扫码和看历史。

**Q：`TIMEOUT` 了要不要重发？**

不要。任务已经在后台队列里执行，重发会产生重复作品。用 `matrix_task_status` 查。
想缩短等待就调大 `timeout` 参数或 `MATRIX_PUBLISH_TIMEOUT`。

**Q：小红书必须有封面吗？**

是。`cover_path` 不传的话小红书发布器拿不到封面，会失败。

---

## 9. 自检

```bash
python mcp_server/_smoke_client.py
```

会以真实 MCP 客户端身份拉起 server，依次验证：握手、7 个工具清单、
`matrix_list_platforms`、`matrix_health`、`matrix_list_accounts`。

只读，不会发布任何内容。

真实发布试用（**会真的发出去**，测完记得去平台删）：

```bash
python mcp_server/_try_publish.py douyin 1
# 参数：平台 account_id [视频路径]
```

它会先调 `matrix_check_login`，再跑 `dry_run`，最后真实发布并打印 `task_id`。
视频默认取数据目录下的 `_mcp_test.mp4`，需要自己放一个进去。

扫码登录试用（会弹出浏览器，**需要人拿手机扫**）：

```bash
python mcp_server/_try_login.py tencent 7
python mcp_server/_try_login.py xhs          # 新建账号
```

---

## 10. 目录结构

```
mcp_server/
├── __init__.py        注入 sys.path，让任意 cwd 都能 import
├── __main__.py        入口：单实例锁 + stdio 启服务
├── stdio_guard.py     把 stdout 从 MCP 协议线上摘下来（Windows 必需）
├── server.py          MCPServer 实例与 8 个 tool 的定义
├── service.py         业务实现：账号、登录、媒体校验、队列、发布、状态
├── settings.py        数据目录探测、白名单、超时等配置
├── lock.py            跨平台文件锁（Windows msvcrt / POSIX flock）
├── requirements.txt
├── README.md
├── _smoke_client.py   本地联调脚本（只读）
├── _try_publish.py    真实发布试用（会发出去）
└── _try_login.py      扫码登录试用（会弹窗口）
```

业务逻辑不在这个目录里，而是复用：

- `desktop/core/publisher.py` —— 单任务发布（纯 Python）
- `desktop/core/auth.py` —— cookie 有效性判定（纯 Python）
- `desktop/core/database.py` —— SQLite 数据层
- `desktop/core/paths.py` / `config.py` —— 路径与配置

所以改发布逻辑**只需要改一处**，桌面客户端和 MCP 同时生效。

---

## 11. 设计取舍（给后续维护者）

- **为什么用 stdio 而不是 HTTP**：执行侧全是本机操作（Chrome、本地视频、cookie 文件），
  stdio 由宿主托管进程生命周期，不用管端口、鉴权、常驻。
- **为什么全局串行**：四个上传器都会启动 Chrome，账号 cookie 文件也是共享的。
  并发不会更快，只会触发风控。`_EXEC_LOCK` + 单 worker 线程是刻意的。
- **为什么不用 MCP 的 resources 暴露账号**：DSH 等客户端只桥接 tools，
  resources 会被静默忽略。全部做成 tool 才是可移植的。
- **为什么错误用返回值不用异常**：异常在 MCP 里变成 `isError`，AI 读不到原因，
  也就没法自己改参数重试。
- **为什么要 `stdio_guard`**：业务代码（4 个 uploader）有大量 `print()`，桌面端靠它
  显示进度。MCP 的 stdout 是协议管线，一行普通文本就会让客户端断连。选择在进程边界
  一次性改道，而不是去改 60 多处 `print` —— 后者会被上游同步覆盖，也没法拦住
  子进程和第三方库的输出。
- **为什么登录校验要真开浏览器**：只查 cookie 文件非空会误报「已登录」，结果是发布
  流程白等一分钟才失败，AI 还会以为是工具坏了。宁可 `check_login` 多花 6–9 秒。
- **为什么登录要拆成 `login_flow.py`**：它原本和 `LoginWorker`（QThread）挤在一个文件里，
  import 就会把 PySide6 拖进 MCP 进程。拆开后桌面端 `login_service.py` 仍然导出同名符号，
  UI 一行不用改，MCP 侧只加载纯 Python 部分。
- **为什么要在 MCP 里做登录**：一开始以为「无头浏览器出不了二维码」就放弃，其实二维码
  不需要由 AI 传输，只要浏览器**有头**就行。四个 `*_setup` 本来就写死 `headless=False`，
  缺的只是把窗口从屏幕外拉回来看得见的地方。不做登录，账号一过期整条链路就断。


