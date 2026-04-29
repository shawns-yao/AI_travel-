# AI Travel Agent Platform

一个全栈多 Agent 旅行规划项目：React 前端负责产品化展示，FastAPI 后端负责 Agent 编排、记忆、外部工具调用、信息缓存和 SSE 流式事件。

当前项目定位是面试作品，不是简单页面 Demo。主链路已经接入 PostgreSQL/pgvector、Redis、高德地图工具、和风天气工具、LLM 配置和 Docker 部署。

## 核心能力

- 多 Agent 编排：`IntentAgent`、`MemoryAgent`、`WeatherAgent`、`BudgetAgent`、`PlannerAgent`、`CriticAgent`
- DAG 执行：依赖校验、并行 wave、重试、失败事件、最终结构化聚合
- Memory：Redis 短期记忆，PostgreSQL/pgvector 长期记忆，Run 级执行记录
- 外部工具：和风天气城市/天气查询，高德地理编码、POI 搜索、路径规划
- 信息缓存：Redis 快缓存，PostgreSQL 持久化兜底
- 前端体验：SSE 生成过程、方案对比、行程编辑、历史行程、实时/兜底地图
- 工程化：Docker Compose、GitHub Actions、pytest、TypeScript build

## 技术栈

- Frontend：React 18、TypeScript、Vite、Tailwind CSS、shadcn/ui、Zustand、TanStack Query
- Backend：FastAPI、Pydantic、SQLAlchemy Async、SSE
- Infra：PostgreSQL 16 + pgvector、Redis 7、Nginx、Docker Compose
- AI：OpenAI-compatible API / Anthropic API

## 密钥策略

真实 API Key 只放在本机环境文件或部署平台的 Secret 里，不能提交到 Git。

本项目已经忽略：

```text
.env
.env.*
server/.env
server/.env.*
```

仓库里只提交：

```text
.env.example
server/.env.example
```

如果你之前在前端“服务配置”页面填写过 Key，那些 Key 存在浏览器 `localStorage`，不会跟着 Git 上传。部署时仍然建议写入 `server/.env` 或 GitHub/Vercel/服务器 Secret。

## 环境变量

复制后填写真实值：

```powershell
Copy-Item server/.env.example server/.env
Copy-Item .env.example .env
```

`server/.env`：

```env
DATABASE_URL=postgresql+asyncpg://travel:travel@localhost:15432/travel
REDIS_URL=redis://localhost:16379

QWEATHER_API_KEY=
QWEATHER_GEO_BASE_URL=https://geoapi.qweather.com
QWEATHER_WEATHER_BASE_URL=https://devapi.qweather.com

AMAP_API_KEY=
AMAP_SECURITY_JS_CODE=
AMAP_BASE_URL=https://restapi.amap.com

LLM_PROVIDER=openai-compatible
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=
EMBEDDING_MODEL=text-embedding-v3

JWT_SECRET=change-me-in-production
```

说明：

- `LLM_API_KEY`：OpenAI-compatible 或 Anthropic 的服务端 Key
- `DASHSCOPE_API_KEY`：兼容旧配置，可不填
- `AMAP_API_KEY`：高德 Web 服务 Key，用于后端地理编码、POI 和路径规划
- 高德 Web JS Key 如果要给浏览器地图用，可以在页面“服务配置”里填；生产环境建议给 Key 配域名白名单

## 本地开发

启动数据库和缓存：

```powershell
docker compose up -d postgres redis
```

启动后端：

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir . --host 127.0.0.1 --port 8001 --reload
```

启动前端：

```powershell
corepack pnpm install
corepack pnpm dev --host 127.0.0.1 --port 5173
```

访问：

```text
http://127.0.0.1:5173
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/health
```

## Docker 部署

准备密钥：

```powershell
Copy-Item server/.env.example server/.env
# 编辑 server/.env，填入 LLM_API_KEY、QWEATHER_API_KEY、AMAP_API_KEY 等
```

一键启动完整栈：

```powershell
docker compose up --build
```

服务地址：

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8001/api/health
Postgres: localhost:15432
Redis:    localhost:16379
```

停止：

```powershell
docker compose down
```

清理数据库卷：

```powershell
docker compose down -v
```

## 测试与构建

后端测试：

```powershell
$env:DATABASE_URL='postgresql+asyncpg://travel:travel@localhost:15432/travel'
$env:REDIS_URL='redis://localhost:16379'
.\server\.venv\Scripts\python.exe -m pytest server\tests -q
```

前端构建：

```powershell
corepack pnpm build
```

Docker 镜像构建：

```powershell
docker build -f docker/Dockerfile.api -t travel-agent-api:local server
docker build -f docker/Dockerfile.web -t travel-agent-web:local .
```

## GitHub 上传前检查

上传前先跑：

```powershell
git status --short
git ls-files | Select-String -Pattern '(^|/)\.env$|\.pem$|\.key$'
```

确认没有 `server/.env`、`.env`、私钥文件、日志文件进入暂存区。

添加远程仓库：

```powershell
git remote set-url origin https://github.com/shawns-yao/AI_travel-.git
git branch -M main
git push -u origin main
```

如果 GitHub Actions 需要外部 API，把这些配置放进仓库的 `Settings -> Secrets and variables -> Actions`：

```text
LLM_API_KEY
DASHSCOPE_API_KEY
QWEATHER_API_KEY
AMAP_API_KEY
```

## 当前边界

这个项目已经能作为 Agent 项目继续扩展，但还不是工业级生产系统。后续最值得补：

- OAuth 和真实多用户隔离
- Hotel/Food/Attraction/Traffic 拆成独立 Agent
- 多人协作规划与冲突协商
- Alembic 迁移脚本
- 更完整的前端测试和端到端测试
