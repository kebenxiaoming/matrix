# matrix
matrix是**视频矩阵内容分发系统**的脚本代码，基于python3，旨在借助playwright实现自动化发布视频到各个社交媒体平台


## 💡Feature
- 目前支持的中国主流社交媒体平台：
  - 抖音
  - 视频号
  - 小红书
  - 快手(todo)

- 登录(schedule)
- 自动上传(cron)
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

需使用supervisor守护进程完成脚本的管理

1、登陆脚本

```
python3 user_queue_login.py 1 //此字段是登陆类型：1：抖音；2：视频号；3：小红书

```

2、视频上传脚本

```
python3 publish_video_queue.py 无需参数，不区分平台，按用户发布顺序逐一发布视频

```

参考项目：
- https://github.com/dreammis/social-auto-upload
- https://github.com/wanghaisheng/tiktoka-studio-uploader
- https://github.com/Superheroff/douyin_uplod
- https://github.com/lishang520/DouYin-Auto-Upload.git

---