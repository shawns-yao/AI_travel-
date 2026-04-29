# AI Travel Agent Platform

一个全栈多 Agent 旅行规划项目：React 前端负责产品化展示，FastAPI 后端负责 Agent 编排、记忆、外部工具调用、信息缓存和 SSE 流式事件。

当前项目定位是面试作品，不是简单页面 Demo。主链路已经接入 PostgreSQL/pgvector、Redis、高德地图工具、和风天气工具、LLM 配置和 Docker 部署。

![Home Page](docs/images/screenshot-home.png)

![Planning](docs/images/screenshot-planning.png)

![Result](docs/images/screenshot-result.png)

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
