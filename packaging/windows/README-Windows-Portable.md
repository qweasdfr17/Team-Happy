# Team-Happy Windows 便携版

## 你需要提前安装

**必须安装 Python 3.12+**。
前往 https://www.python.org/downloads/ 下载安装。
安装时务必勾选 **Add Python to PATH**。

无需 Git / Node.js / pnpm / WSL / Docker。

可选：安装 FFmpeg 并加入 PATH 后，可启用更完整的视频缩略图/尾帧提取能力；未安装也不影响核心功能启动。

## 启动

双击 `start-team-happy.bat`。
首次启动会自动下载 Python 依赖（~500MB，需几分钟），后续启动秒开。
浏览器自动打开 http://127.0.0.1:1242 ，免登录直接进入。

## 配置 API

进入「设置 → 供应商」，添加你的 API 密钥。

## 数据保存

所有项目、剧本、生成素材、配置保存在 `data/` 目录。
换电脑：复制整个 Team-Happy 目录即可迁移，API 密钥需重新配置。

## 关闭

关闭黑色命令行窗口即停止。

## 端口

默认 1242。如需修改，设环境变量 `LISTEN_PORT` 或在 bat 中改。
