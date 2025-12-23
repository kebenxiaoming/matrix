# 快手自动化工具

基于 Playwright 的快手平台自动化工具，支持视频上传、批量上传和直播功能。

##  功能特性

### 1. 账号管理
- **Cookie 认证**: 自动检测和验证账号 Cookie 有效性
- **登录生成**: 支持二维码登录，自动保存账号信息
- **状态缓存**: 使用 Redis 缓存登录状态，提高效率

### 2. 视频上传 (`KuaiShouVideo`)
-  自动上传视频文件
-  自定义视频标题和预览图
-  支持话题标签
-  支持定时发布
-  自动等待上传完成
-  Cookie 自动更新保存

### 3. 批量上传 (`KuaiShouBatchUpload`) ⭐ 新功能
- **矩阵相乘算法**: 视频矩阵 × 账号矩阵 = 批量任务
- **并发控制**: 支持顺序或并发执行（可配置）
- **任务管理**: 自动生成所有视频×账号组合
- **进度跟踪**: 实时显示任务进度和统计信息
- **错误处理**: 单个任务失败不影响其他任务
- **结果统计**: 完成后显示成功/失败统计

**示例**:
```
视频矩阵: [视频1, 视频2, 视频3]
账号矩阵: [账号1, 账号2]
结果: 6个上传任务 (3×2)
```

### 4. 直播功能 (`KuaiShouLive`) ⭐ 新功能
-  自动创建直播
-  设置直播标题和封面
-  视频文件作为直播源（通过屏幕共享）
-  自动循环播放视频
-  支持直播控制（开始/结束）

##  快速开始

### 安装依赖

```bash
pip install playwright asyncio redis
playwright install chromium
```

### 配置要求

需要创建 `conf.py` 文件，包含 Redis 配置：

```python
REDIS_CONF = {
    "host": "localhost",
    "port": 6379,
    "select_db": 0,
    "password": ""  # 如果有密码则填写
}
```

### 使用示例

#### 1. 单个视频上传

```python
import asyncio
from main import KuaiShouVideo

async def upload_single():
    uploader = KuaiShouVideo(
        title="我的视频标题",
        file_path="/path/to/video.mp4",
        video_preview="/path/to/preview.jpg",
        tags=["标签1", "标签2"],
        publish_date=0,  # 0=立即发布
        account_file="account.json"
    )
    await uploader.main()

asyncio.run(upload_single())
```

#### 2. 批量上传（矩阵相乘）

```python
import asyncio
from main import KuaiShouBatchUpload

async def batch_upload():
    # 视频矩阵（一行）
    videos = [
        {
            'title': '视频1',
            'file_path': 'video1.mp4',
            'video_preview': 'preview1.jpg',
            'tags': ['标签1'],
            'publish_date': 0
        },
        {
            'title': '视频2',
            'file_path': 'video2.mp4',
            'video_preview': 'preview2.jpg',
            'tags': [],
            'publish_date': 0
        }
    ]
    
    # 账号矩阵（一列）
    accounts = [
        'account1.json',
        'account2.json',
        'account3.json'
    ]
    
    # 创建批量上传器（2个视频 × 3个账号 = 6个任务）
    batch = KuaiShouBatchUpload(
        video_matrix=videos,
        account_matrix=accounts,
        max_concurrent=1,      # 并发数
        delay_between_uploads=5  # 任务间延迟（秒）
    )
    
    # 执行批量上传
    results = await batch.upload_all()
    
    # 查看结果
    for result in results:
        print(f"{result['task_id']}: {result['status']}")

asyncio.run(batch_upload())
```

#### 3. 便捷函数

```python
from main import create_batch_upload

batch = create_batch_upload(videos, accounts, max_concurrent=1)
await batch.main()
```

#### 4. 直播功能

```python
import asyncio
from main import KuaiShouLive

async def start_live():
    live = KuaiShouLive(
        title="我的直播标题",
        video_path="/path/to/video.mp4",  # 用于直播的视频
        cover_image="/path/to/cover.jpg",
        account_file="account.json"
    )
    await live.main()

asyncio.run(start_live())
```

##  技术架构

### 核心技术
- **Playwright**: 浏览器自动化框架
- **Asyncio**: 异步并发处理
- **Redis**: 状态缓存和任务队列

### 设计模式
- **矩阵算法**: 视频×账号组合生成
- **任务队列**: 批量任务管理
- **并发控制**: 信号量控制并发数
- **错误隔离**: 单个任务失败不影响整体

##  主要类和方法

### `KuaiShouVideo`
- `upload()`: 执行视频上传
- `set_schedule_time_ks()`: 设置定时发布
- `main()`: 主入口方法

### `KuaiShouBatchUpload`
- `generate_task_matrix()`: 生成任务矩阵
- `upload_all()`: 执行所有任务
- `upload_single_task()`: 执行单个任务
- `print_summary()`: 打印统计信息

### `KuaiShouLive`
- `start_live()`: 开始直播
- `create_video_player_page()`: 创建视频播放页面

### 工具函数
- `cookie_auth()`: Cookie 验证
- `ks_setup()`: 账号设置
- `ks_cookie_gen()`: 生成 Cookie
- `cache_data()`: Redis 缓存写入
- `cache_get_data()`: Redis 缓存读取
- `create_batch_upload()`: 批量上传便捷函数

##  配置说明

### 批量上传参数
- `max_concurrent`: 最大并发数（建议1-3，避免账号风险）
- `delay_between_uploads`: 任务间延迟（秒，建议5-10秒）

### 账号文件格式
账号文件为 JSON 格式，包含浏览器存储状态（Cookie 等），由 `ks_cookie_gen()` 自动生成。

##  注意事项

1. **账号安全**: 建议设置合理的并发数和延迟，避免触发平台风控
2. **Cookie 管理**: 定期检查 Cookie 有效性，使用 `cookie_auth()` 验证
3. **直播功能**: 屏幕共享需要手动选择视频播放窗口
4. **错误处理**: 批量上传会自动记录失败任务，可查看详细错误信息

##  更新日志

### v2.0 (最新)
-  新增批量上传功能（矩阵相乘算法）
-  新增直播功能
-  支持并发控制
-  添加任务统计和进度跟踪
-  优化错误处理机制

### v1.0
-  基础视频上传功能
-  Cookie 管理和验证
-  定时发布支持



## 本项目仅供学习交流使用。

