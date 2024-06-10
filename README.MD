# matrix
matrix是**视频矩阵内容分发系统**的脚本代码，基于python，旨在借助playwright实现自动化发布视频到抖音、快手、视频号、小红书等各个社交媒体平台

## 版本要求
 
- Python 3.8 or higher.（作者用的是Python 3.12+）
- Windows 10+, Windows Server 2016+ or Windows Subsystem for Linux (WSL).
- MacOS 12 Monterey, MacOS 13 Ventura, or MacOS 14 Sonoma.
- Debian 11, Debian 12, Ubuntu 20.04 or Ubuntu 22.04.

## 💡Feature
- 目前支持的中国主流社交媒体平台：
  - 抖音
  - 视频号
  - 小红书
  - 快手(doing，上传视频初步完成)

- 登录(脚本)
- 自动上传(脚本)
- cookie 管理(file)
- 国外平台proxy 设置（todo)
- 多线程上传（todo)
- slack 推送（todo)


# 💾Installation
```
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
playwright install chromium
```

# 使用方法

一、修改conf.py配置文件
```
BASE_PATH = 根目录绝对路径（用于文件路径处理）

REDIS_CONF : Redis配置（用于记录登录二维码，登录状态等）

MYSQL_CONF : Mysql配置（用于登录或发送视频数据库队列）
```

二、导入数据库
主要用于登录和发送数据库队列。

```
将database目录中的matrix.sql导入数据库,具体表结构也不复杂，请参考sql中的注释
```

三、需使用supervisor守护进程完成脚本的管理

1、登陆脚本

```
python3 user_queue_login.py 1 //此字段是登陆类型：1：抖音；2：视频号；3：小红书

注：小红书登录需要开启flask的请求服务，用来获取小红书的x-s和x-t

需要将xhs-api目录下的app2024.py服务先启动。

```

2、视频上传脚本

```
python3 publish_video_queue.py 无需参数，不区分平台，按用户发布顺序逐一发布视频

```
四、如何获取数据

```
1、登录二维码可以从redis中直接取值(base64的数据)，具体获取数据方式请查阅代码

2、有时候抖音登录会出现需要发送短信的情况，也已经处理，可以从缓存获取标识来处理

3、登陆的cookie都存在各个平台代码（如抖音：douyin_uploader）目录的account目录(如果没有请先创建)中，请注意需要有目录权限，登陆后用户信息会存储到mx_account_info表中

4、自己可以尝试开启或者关闭headless（是否在运行过程开启浏览器界面）

```

五、有任何问题请在issue中留言。

六、参考项目：
- https://github.com/dreammis/social-auto-upload
- https://github.com/wanghaisheng/tiktoka-studio-uploader
- https://github.com/Superheroff/douyin_uplod
- https://github.com/lishang520/DouYin-Auto-Upload.git
- https://github.com/ReaJason/xhs

---