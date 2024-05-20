/*
 Navicat Premium Data Transfer

 Source Server         : 本地数据库
 Source Server Type    : MySQL
 Source Server Version : 80029
 Source Host           : localhost:3306
 Source Schema         : matrix

 Target Server Type    : MySQL
 Target Server Version : 80029
 File Encoding         : 65001

 Date: 20/05/2024 16:37:34
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for mx_account_info
-- ----------------------------
DROP TABLE IF EXISTS `mx_account_info`;
CREATE TABLE `mx_account_info`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `queue_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '队列ID：记录哪个队列登录的此用户',
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `account_id` varchar(225) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '第三方平台ID',
  `username` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '第三方用户名',
  `avatar` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '第三方头像',
  `extend` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '其他扩展数据，如粉丝数等',
  `type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录类型：1：抖音；2：视频号；3：小红书',
  `status` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录信息：1：登录；0：未登录；2：已过期',
  `created_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 78 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_account_login_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_account_login_queue`;
CREATE TABLE `mx_account_login_queue`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录类型：1：抖音；2：视频号；3：小红书',
  `status` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '队列状态:0:未执行;1:执行中;2:执行成功;3:执行失败',
  `created_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 70 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_attachment
-- ----------------------------
DROP TABLE IF EXISTS `mx_attachment`;
CREATE TABLE `mx_attachment`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `project_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '文件夹分类ID',
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '文件类型：1：图片；2：视频',
  `original_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '原始文件名',
  `preview` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '预览图链接',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '现在文件名',
  `mime_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT 'mime类型',
  `path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '本地路径',
  `url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '远程访问链接',
  `size` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '文件大小，单位：字节',
  `file_md5` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '文件MD5',
  `created_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 26 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_dept
-- ----------------------------
DROP TABLE IF EXISTS `mx_dept`;
CREATE TABLE `mx_dept`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '部门名称',
  `parent_id` bigint(0) NOT NULL DEFAULT 0 COMMENT '父节点id',
  `tree_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '父节点id路径',
  `sort` int(0) NULL DEFAULT 0 COMMENT '显示顺序',
  `status` tinyint(0) NOT NULL DEFAULT 1 COMMENT '状态(1:正常;0:禁用)',
  `deleted_at` tinyint(0) UNSIGNED NULL DEFAULT NULL COMMENT '逻辑删除标识(1:已删除;0:未删除)',
  `created_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '更新时间',
  `create_by` bigint(0) NULL DEFAULT NULL COMMENT '创建人ID',
  `update_by` bigint(0) NULL DEFAULT NULL COMMENT '修改人ID',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '部门表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_dict
-- ----------------------------
DROP TABLE IF EXISTS `mx_dict`;
CREATE TABLE `mx_dict`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `type_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '字典类型编码',
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '字典项名称',
  `value` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '字典项值',
  `sort` int(0) NULL DEFAULT 0 COMMENT '排序',
  `status` tinyint(0) NULL DEFAULT 0 COMMENT '状态(1:正常;0:禁用)',
  `defaulted` tinyint(0) NULL DEFAULT 0 COMMENT '是否默认(1:是;0:否)',
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '备注',
  `created_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '字典数据表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_dict_type
-- ----------------------------
DROP TABLE IF EXISTS `mx_dict_type`;
CREATE TABLE `mx_dict_type`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT COMMENT '主键 ',
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '类型名称',
  `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '类型编码',
  `status` tinyint(1) NULL DEFAULT 0 COMMENT '状态(0:正常;1:禁用)',
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备注',
  `create_time` datetime(0) NULL DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime(0) NULL DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `type_code`(`code`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '字典类型表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_menu
-- ----------------------------
DROP TABLE IF EXISTS `mx_menu`;
CREATE TABLE `mx_menu`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `cate` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '菜单类型：0：平台菜单；1：站点菜单',
  `parent_id` bigint(0) NOT NULL COMMENT '父菜单ID',
  `tree_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '父节点ID路径',
  `name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '菜单名称',
  `type` tinyint(0) NOT NULL COMMENT '菜单类型(1:菜单 2:目录 3:外链 4:按钮)',
  `path` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '路由路径(浏览器地址栏路径)',
  `component` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '组件路径(vue页面完整路径，省略.vue后缀)',
  `perm` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '权限标识',
  `visible` tinyint(1) NOT NULL DEFAULT 1 COMMENT '显示状态(1-显示;0-隐藏)',
  `sort` int(0) NULL DEFAULT 0 COMMENT '排序',
  `icon` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '菜单图标',
  `redirect` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '跳转路径',
  `created_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '更新时间',
  `always_show` tinyint(0) NULL DEFAULT NULL COMMENT '【目录】只有一个子路由是否始终显示(1:是 0:否)',
  `keep_alive` tinyint(0) NULL DEFAULT NULL COMMENT '【菜单】是否开启页面缓存(1:是 0:否)',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 145 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '菜单管理' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_project
-- ----------------------------
DROP TABLE IF EXISTS `mx_project`;
CREATE TABLE `mx_project`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '项目名',
  `parent_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '父级ID',
  `level` tinyint(0) UNSIGNED NOT NULL DEFAULT 1 COMMENT '等级',
  `tree_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '树形父级ID，多个ID用,分割',
  `sort` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '排序值',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  `created_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_publish_info
-- ----------------------------
DROP TABLE IF EXISTS `mx_publish_info`;
CREATE TABLE `mx_publish_info`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `attachment_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '文件附件ID',
  `douyin` json NOT NULL COMMENT '类型：1：抖音；2：视频号；3：小红书；4：快手',
  `kuaishou` json NOT NULL COMMENT '视频标题',
  `xhs` json NOT NULL COMMENT '视频描述',
  `sph` json NOT NULL COMMENT '位置',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  `created_at` int(0) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 13 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_publish_task
-- ----------------------------
DROP TABLE IF EXISTS `mx_publish_task`;
CREATE TABLE `mx_publish_task`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布任务用户ID',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '任务标题',
  `created_at` int(0) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 60 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_publish_task_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_publish_task_queue`;
CREATE TABLE `mx_publish_task_queue`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `task_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '任务ID',
  `task_title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '任务标题',
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布任务用户ID',
  `type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '任务类型：1：抖音；2：视频号；3：小红书；4：快手',
  `account_info_id` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '第三方授权用户ID，多个用,分开',
  `attachment_id` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频ID，多个用,分开',
  `video_num` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '视频数量',
  `account_num` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '账号数量',
  `total_num` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '总需发布数量',
  `publish_num` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '已发布成功数量',
  `fail_num` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布失败数量',
  `status` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布状态：0：未开始；1：发布中；2：发布成功；3：发布失败；4：未登录发布失败',
  `created_at` int(0) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 58 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_publish_task_video_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_publish_task_video_queue`;
CREATE TABLE `mx_publish_task_video_queue`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `uid` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布任务用户ID',
  `type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '上传类型：1：抖音；2：视频号；3：小红书；4：快手',
  `task_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '总任务ID',
  `task_queue_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布任务的ID',
  `account_info_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '第三方授权用户ID',
  `attachment_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '视频附件ID',
  `title` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '发布标题',
  `tags` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '发布标签',
  `preview` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '发布预览图',
  `path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频本地路径',
  `url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '视频远程路径',
  `location` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '定位城市',
  `publish_date` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '发布时间',
  `status` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '状态：0：未开始；1：发布中；2：发布成功；3：发布失败；4：未登录发布失败',
  `created_at` int(0) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 58 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_role
-- ----------------------------
DROP TABLE IF EXISTS `mx_role`;
CREATE TABLE `mx_role`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '角色名称',
  `code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '角色编码',
  `sort` int(0) NULL DEFAULT NULL COMMENT '显示顺序',
  `status` tinyint(1) NULL DEFAULT 1 COMMENT '角色状态(1-正常；0-停用)',
  `data_scope` tinyint(0) NULL DEFAULT NULL COMMENT '数据权限(0-所有数据；1-部门及子部门数据；2-本部门数据；3-本人数据)',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '逻辑删除标识(0-未删除；1-已删除)',
  `created_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '更新时间',
  `updated_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `name`(`name`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 129 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '角色表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_role_menu
-- ----------------------------
DROP TABLE IF EXISTS `mx_role_menu`;
CREATE TABLE `mx_role_menu`  (
  `role_id` bigint(0) NOT NULL COMMENT '角色ID',
  `menu_id` bigint(0) NOT NULL COMMENT '菜单ID'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '角色和菜单关联表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_site
-- ----------------------------
DROP TABLE IF EXISTS `mx_site`;
CREATE TABLE `mx_site`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '站点名',
  `logo` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT 'LOGO链接',
  `member_id` bigint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '管理员ID',
  `expire_type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '过期类型：1：有限；2：无限',
  `expire_time` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '过期时间：类型为1有效',
  `remark` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '备注',
  `status` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '状态',
  `open_status` tinyint(0) UNSIGNED NOT NULL DEFAULT 1 COMMENT '开启状态：1：开启；0：关闭',
  `updated_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  `created_at` int(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_user
-- ----------------------------
DROP TABLE IF EXISTS `mx_user`;
CREATE TABLE `mx_user`  (
  `id` int(0) NOT NULL AUTO_INCREMENT,
  `type` tinyint(0) UNSIGNED NOT NULL DEFAULT 0 COMMENT '1：管理员',
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '用户名',
  `nickname` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '昵称',
  `gender` tinyint(1) NULL DEFAULT 1 COMMENT '性别((1:男;2:女))',
  `password` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '密码',
  `dept_id` int(0) NULL DEFAULT NULL COMMENT '部门ID',
  `avatar` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '用户头像',
  `mobile` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '联系方式',
  `status` tinyint(1) NULL DEFAULT 1 COMMENT '用户状态((1:正常;0:禁用))',
  `email` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '用户邮箱',
  `salt` char(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '加密盐',
  `deleted_at` int(0) UNSIGNED NULL DEFAULT NULL COMMENT '逻辑删除标识(NULL:未删除;有时间:已删除)',
  `created_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(0) UNSIGNED NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `login_name`(`username`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 290 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '用户信息表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for mx_user_role
-- ----------------------------
DROP TABLE IF EXISTS `mx_user_role`;
CREATE TABLE `mx_user_role`  (
  `user_id` bigint(0) NOT NULL COMMENT '用户ID',
  `role_id` bigint(0) NOT NULL COMMENT '角色ID',
  PRIMARY KEY (`user_id`, `role_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '用户和角色关联表' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
