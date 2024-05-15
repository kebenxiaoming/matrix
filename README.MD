# matrix
matrix是**视频矩阵内容分发系统**的脚本代码，基于python3，旨在借助playwright实现自动化发布视频到各个社交媒体平台

## 💡Feature
- 目前支持的中国主流社交媒体平台：
  - 抖音
  - 视频号
  - 小红书
  - 快手(todo)

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
将database目录中的matrix.sql导入数据库，修改数据其中mx_video表中就是要上传的视频数据，可以修改为本地的文件

至于表中的account_id，请结合自己创建的用户表处理。

mx_video:视频数据表

CREATE TABLE `mx_video`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `flag` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '标识：1：大于100M；0：其他',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频标题',
  `description` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频描述',
  `tag` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频标签',
  `img` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频预览图',
  `video_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频地址本地完整路径',
  `created_at` int(10) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(10) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

mx_user_login_queue:模拟视频创作平台登录队列表

CREATE TABLE `mx_user_login_queue`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `account_id` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `type` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录类型：1：抖音；2：视频号',
  `status` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '队列状态:0:未执行;1:执行中;2:执行成功;3:执行失败',
  `created_at` int(10) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(10) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

mx_publish_video_queue:视频发布队列表（注意要发布视频要先登录）

CREATE TABLE `mx_publish_video_queue`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `account_id` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `type` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '上传类型：1：抖音；2：视频号',
  `video_id` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '视频ID',
  `publish_date` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '发布时间',
  `location` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '定位城市',
  `status` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '状态：0：未开始；1：发布中；2：发布成功；3：发布失败；4：未登录发布失败',
  `created_at` int(10) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(10) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = DYNAMIC;

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

3、登陆的cookie都存在各个平台代码（如抖音：douyin_uploader）目录的account目录(如果没有请先创建)中，请注意需要有目录权限

```

五、有任何问题请在issue中留言。

六、参考项目：
- https://github.com/dreammis/social-auto-upload
- https://github.com/wanghaisheng/tiktoka-studio-uploader
- https://github.com/Superheroff/douyin_uplod
- https://github.com/lishang520/DouYin-Auto-Upload.git

---