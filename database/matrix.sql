/*
 Navicat Premium Data Transfer

 Source Server         : local
 Source Server Type    : MySQL
 Source Server Version : 50738 (5.7.38-log)
 Source Host           : 127.0.0.1:3306
 Source Schema         : matrix

 Target Server Type    : MySQL
 Target Server Version : 50738 (5.7.38-log)
 File Encoding         : 65001

 Date: 13/06/2024 17:16:40
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for mx_account_info
-- ----------------------------
DROP TABLE IF EXISTS `mx_account_info`;
CREATE TABLE `mx_account_info`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `queue_id` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '队列ID：记录哪个队列登录的此用户',
  `uid` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `account_id` varchar(225) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '第三方平台ID',
  `username` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '第三方用户名',
  `avatar` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '第三方头像',
  `extend` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '其他扩展数据，如粉丝数等',
  `type` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录类型：1：抖音；2：视频号；3：小红书',
  `status` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录信息：1：登录；0：未登录；2：已过期',
  `created_at` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of mx_account_info
-- ----------------------------
INSERT INTO `mx_account_info` VALUES (1, 1, 1, 'sunnier_tt', '王者荣耀菜狗【娱乐局】', 'https://p2-pro.a.yximgs.com/uhead/AB/2021/01/30/12/BMjAyMTAxMzAxMjU1MTVfMjI0MTQ0Mjk0NV8yX2hkMTQ2Xzg2MA==_s.jpg', '', 4, 1, 1717055817, 0);
INSERT INTO `mx_account_info` VALUES (2, 71, 1, '873667672', '拉普达', 'https://p26.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-i-0813_oUezNAglTAPgABZADN2tB93CDlObIR7AAYegEn.jpeg?from=2956013662', '', 1, 1, 1718269634, 0);
INSERT INTO `mx_account_info` VALUES (3, 72, 1, 'sphum31Urfh9d2g', '拉普达2023', 'https://wx.qlogo.cn/finderhead/jJtbwFuzNwDOpj5tZGvgVy8gOZuEZW9FBNS5O4GHCvo3yAuy8rB4PQ/0', '', 2, 1, 1718269698, 0);

-- ----------------------------
-- Table structure for mx_account_login_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_account_login_queue`;
CREATE TABLE `mx_account_login_queue`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `uid` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
  `type` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '登录类型：1：抖音；2：视频号；3：小红书',
  `status` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '队列状态:0:未执行;1:执行中;2:执行成功;3:执行失败',
  `created_at` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 73 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of mx_account_login_queue
-- ----------------------------
INSERT INTO `mx_account_login_queue` VALUES (70, 1, 4, 2, 1718269235, 1718269235);
INSERT INTO `mx_account_login_queue` VALUES (71, 1, 1, 2, 1718269235, 1718269235);
INSERT INTO `mx_account_login_queue` VALUES (72, 1, 2, 2, 1718269235, 1718269235);

-- ----------------------------
-- Table structure for mx_publish_task_video_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_publish_task_video_queue`;
CREATE TABLE `mx_publish_task_video_queue`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `uid` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '发布任务用户ID',
  `type` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '上传类型：1：抖音；2：视频号；3：小红书；4：快手',
  `account_info_id` bigint(20) UNSIGNED NOT NULL DEFAULT 0 COMMENT '第三方授权用户ID',
  `title` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '发布标题',
  `tags` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '发布标签',
  `preview` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '发布预览图',
  `path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '视频本地路径',
  `url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '视频远程路径',
  `location` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '定位城市',
  `publish_date` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '发布时间',
  `status` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '状态：0：未开始；1：发布中；2：发布成功；3：发布失败；4：未登录发布失败',
  `created_at` int(10) UNSIGNED NOT NULL COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NOT NULL COMMENT '更新时间',
  `deleted_at` int(10) UNSIGNED NULL DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 59 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of mx_publish_task_video_queue
-- ----------------------------
INSERT INTO `mx_publish_task_video_queue` VALUES (56, 1, 4, 1, '扑克牌上的Q代表什么', '', 'image/1.png', 'video/1.mp4', 'video/1.mp4', '重庆市', '', 2, 1706583493, 1706583493, NULL);
INSERT INTO `mx_publish_task_video_queue` VALUES (57, 1, 1, 2, '扑克牌上的Q代表什么', '', 'image/1.png', 'video/1.mp4', 'video/1.mp4', '重庆市', '2024-06-13 20:00:00', 2, 1706583493, 1706583493, NULL);
INSERT INTO `mx_publish_task_video_queue` VALUES (58, 1, 2, 3, '扑克牌上的Q代表什么', '', 'image/1.png', 'video/1.mp4', 'video/1.mp4', '重庆市', '2024-06-13 20:00:00', 2, 1706583493, 1706583493, NULL);

-- ----------------------------
-- Table structure for mx_user
-- ----------------------------
DROP TABLE IF EXISTS `mx_user`;
CREATE TABLE `mx_user`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '1：管理员',
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '用户名',
  `nickname` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '昵称',
  `gender` tinyint(1) NULL DEFAULT 1 COMMENT '性别((1:男;2:女))',
  `password` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '密码',
  `dept_id` int(11) NULL DEFAULT NULL COMMENT '部门ID',
  `avatar` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '用户头像',
  `mobile` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '联系方式',
  `status` tinyint(1) NULL DEFAULT 1 COMMENT '用户状态((1:正常;0:禁用))',
  `email` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '用户邮箱',
  `salt` char(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '加密盐',
  `deleted_at` int(10) UNSIGNED NULL DEFAULT NULL COMMENT '逻辑删除标识(NULL:未删除;有时间:已删除)',
  `created_at` int(10) UNSIGNED NULL DEFAULT 0 COMMENT '创建时间',
  `updated_at` int(10) UNSIGNED NULL DEFAULT 0 COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `login_name`(`username`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '用户信息表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of mx_user
-- ----------------------------

SET FOREIGN_KEY_CHECKS = 1;
