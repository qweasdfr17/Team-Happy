# Repository Structure

本文件用于 GitHub 上传前快速理解仓库结构。运行数据、用户项目和本地凭证默认由 `.gitignore` 排除，不应提交到远程仓库。

## Top-Level Layout

```text
.
├── .github/                 # GitHub Actions 与仓库自动化配置
├── agent_runtime_profile/   # 内置 Agent Profile、Skill 与运行提示词
├── alembic/                 # 数据库迁移脚本
├── deploy/                  # Docker / 生产部署配置
├── docs/                    # 使用说明、架构记录、提案和供应商文档
├── frontend/                # React + Vite 前端工作台
├── lib/                     # 核心业务逻辑、生成服务、供应商适配和项目管理
├── openspec/                # 需求与规格文档
├── packaging/               # Windows 便携包与局域网分发脚本
├── public/                  # 后端静态公开资源
├── scripts/                 # 辅助脚本、导入脚本、开发工具
├── server/                  # FastAPI 应用、路由、服务层和 Agent 工具
├── tests/                   # 后端、前端辅助逻辑和集成测试
├── projects/                # 本地用户项目数据，默认不提交
├── vertex_keys/             # 本地云供应商凭证，默认不提交
└── release/                 # 本地打包输出目录，新增产物默认不提交
```

## Important Files

```text
README.md                   # 中文项目说明
README.en.md                # 英文项目说明
CHANGELOG.md                # 版本变更记录
LICENSE                     # AGPL-3.0 许可证
pyproject.toml              # Python 项目元数据与后端依赖
uv.lock                     # Python 依赖锁定
frontend/package.json       # 前端依赖与脚本
frontend/pnpm-lock.yaml     # 前端依赖锁定
.env.example                # 后端环境变量模板
frontend/.env.example       # 前端环境变量模板
.gitignore                  # GitHub 上传忽略规则
```

## Ignored Runtime Data

以下内容属于本地运行环境或用户生产数据，不应上传：

```text
.env
frontend/.env
.venv/
frontend/node_modules/
frontend/dist/
logs/
*.log
.pytest_cache/
.ruff_cache/
projects/*
vertex_keys/*
release/*.zip
```

`projects/.gitkeep`、`projects/.agent_data/.gitkeep`、`projects/.agent_data/transcripts/.gitkeep` 和 `vertex_keys/.gitkeep` 用于保留空目录结构，可以提交。

## Local Development Commands

```bash
uv sync --dev
cp .env.example .env

cd frontend
pnpm install
cp .env.example .env
pnpm dev -- --host 127.0.0.1 --port 5174
```

另开终端启动后端：

```bash
uv run uvicorn server.app:app --host 127.0.0.1 --port 1242
```

## Pre-Upload Checklist

```bash
git status --short
git check-ignore -v .env frontend/.env frontend/node_modules projects/<project-name>
cd frontend && pnpm install --frozen-lockfile
cd .. && uv sync --dev
```

如需提交到公开仓库，请先人工确认 `projects/`、`vertex_keys/`、`.env`、日志和打包产物没有被 `git add -f` 强制加入。
