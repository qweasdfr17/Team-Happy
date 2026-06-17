# Team-Happy Windows 便携启动指南

## 适用场景

纯净 Windows 10/11 64 位系统，不要求 WSL / Git / Node.js / Docker。

## 你需要提前安装

| 软件 | 版本要求 | 下载 |
|------|---------|------|
| Python | 3.12+ | https://www.python.org/downloads/ （安装时勾选 **Add Python to PATH**） |

**仅需 Python**。uv、前端依赖、Python 依赖均由启动脚本自动处理。

## 发布包目录结构

```
Team-Happy/
├── start-team-happy.bat     ← 双击这个启动
├── server/                  ← 后端代码
├── lib/                     ← 核心库
├── frontend/dist/           ← 前端构建产物（pnpm build 后产生）
├── agent_runtime_profile/   ← Agent skills + profiles
├── packaging/windows/       ← 本说明
├── data/                    ← 所有项目数据、配置、数据库（自动创建，换电脑拷贝此项即可迁移）
│   ├── projects/            ← 用户项目
│   └── .arcreel.db          ← SQLite 数据库
├── pyproject.toml
├── uv.lock
└── ...
```

## 启动方式

1. 双击 `start-team-happy.bat`
2. 等待 Python 依赖同步（首次 1-2 分钟，后续秒开）
3. 浏览器自动打开 http://127.0.0.1:1241
4. **免登录**直接进入项目页

## 第一次进入后

1. 打开「设置 → 供应商」页面
2. 配置你需要的 API 供应商密钥（Anthropic / OpenAI / Gemini 等）
3. 创建项目开始使用

## 数据保存在哪里

所有数据在 `data/` 目录下：

- `data/projects/` — 项目文件、剧本、生成素材
- `data/.arcreel.db` — 系统配置、API Key（加密存储）

**换电脑**：复制整个 Team-Happy 目录到新电脑，数据全部保留。注意 API Key 需要在设置页重新配置（加密密钥与机器绑定）。

## 如何关闭

关闭命令行窗口即停止服务。下次双击 `start-team-happy.bat` 继续使用，数据不丢失。

## 端口

默认 1241。如需修改，设置环境变量 `LISTEN_PORT=8080` 或在 bat 里修改。

## 常见问题

**Q: 启动提示 "未找到 Python"**
A: 安装 Python 3.12+，安装时务必勾选 "Add Python to PATH"。安装后重新打开命令行。

**Q: 首次启动很慢**
A: 首次启动需要 `uv sync` 下载 Python 依赖（约 500MB .venv），后续会跳过。

**Q: 浏览器打开后显示空白**
A: 确认 `frontend/dist/index.html` 存在。如果缺失，在项目根执行：
```
cd frontend
pnpm build
```
注意：这需要提前安装 Node.js + pnpm。

**Q: 如何迁移到另一台电脑**
A: 复制整个 Team-Happy 目录。API Key 需要在设置页重新配置。

**Q: 能同时给多人用吗**
A: 当前为单用户免登录模式。如需多人使用，删除 `AUTH_ENABLED=false` 行恢复登录。

**Q: 能部署到公网吗**
A: 不建议。默认绑定 127.0.0.1 仅本机访问。如需公网部署请使用 Docker Compose，并务必设置 AUTH_ENABLED=true。
