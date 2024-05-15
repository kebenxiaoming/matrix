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

 Date: 15/05/2024 15:11:11
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for mx_publish_video_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_publish_video_queue`;
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

-- ----------------------------
-- Records of mx_publish_video_queue
-- ----------------------------
INSERT INTO `mx_publish_video_queue` VALUES (1, 1, 1, 1, '', '', 0, 1703665026, 1703665026, NULL);
INSERT INTO `mx_publish_video_queue` VALUES (2, 1, 2, 1, '', '', 0, 1703665027, 1703665027, NULL);
INSERT INTO `mx_publish_video_queue` VALUES (3, 1, 3, 1, '', '', 0, 1704246407, 1704262695, NULL);

-- ----------------------------
-- Table structure for mx_user_login_queue
-- ----------------------------
DROP TABLE IF EXISTS `mx_user_login_queue`;
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

-- ----------------------------
-- Records of mx_user_login_queue
-- ----------------------------
INSERT INTO `mx_user_login_queue` VALUES (1, 1, 1, 0, 1704437583, 1704437583, NULL);

-- ----------------------------
-- Table structure for mx_video
-- ----------------------------
DROP TABLE IF EXISTS `mx_video`;
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

-- ----------------------------
-- Records of mx_video
-- ----------------------------
INSERT INTO `mx_video` VALUES (1, 0, '问：“青莲居士”指的是？', '', '#公考常识 #每天学习一点点 #公基知识每日一练 #公基', '/video/1/1.png', 'D:\\playwright-project\\basepython\\social-auto-upload-main\\videos\\1\\问：“青莲居士”指的是？.mp4', 1703574734, 1703574734, NULL);

SET FOREIGN_KEY_CHECKS = 1;
