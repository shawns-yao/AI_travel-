# AI Travel Agent Platform

这是一个 React + FastAPI 的全栈多 Agent 旅行规划项目。

## 当前架构

```text
travel/
├── src/                    React + Vite + TypeScript 前端
├── server/                 FastAPI 后端
│   ├── app/api             REST + SSE
│   ├── app/agents          Agent 实现和 prompts
│   ├── app/core            DAG、LLM、工具注册、配置
│   ├── app/memory          Redis 短期记忆 + pgvector 长期记忆
│   ├── app/tools           高德、和风天气等工具
│   ├── app/services        运行服务、信息缓存
│   └── tests               pytest 测试
├── docker                  Dockerfile 和 Nginx 配置
├── docker-compose.yml
└── README.md
```

## 技术栈

- Frontend：React 18、TypeScript、Vite、Tailwind CSS、shadcn/ui、Zustand、TanStack Query
- Backend：FastAPI、Pydantic、SQLAlchemy Async、SSE
- Database：PostgreSQL 16 + pgvector
- Cache：Redis 7
- AI：OpenAI-compatible API / Anthropic API
- Deploy：Docker Compose、Nginx、GitHub Actions

## Agent

当前已实现 6 个 Agent：

- `IntentAgent`：解析目的地、日期、预算、偏好
- `MemoryAgent`：读取短期/长期记忆
- `WeatherAgent`：调用和风天气工具
- `BudgetAgent`：预算分配与风险提示
- `PlannerAgent`：调用高德工具，生成每日行程
- `CriticAgent`：审查方案质量

后续计划拆分：

- `TrafficAgent`
- `HotelAgent`
- `FoodAgent`
- `AttractionAgent`
- `ItineraryOptimizerAgent`

## 启动

完整说明见 `README.md`。

```powershell
Copy-Item server/.env.example server/.env
docker compose up --build
```

访问：

```text
http://127.0.0.1:5173
```

## 环境变量

真实 Key 只放在 `server/.env` 或部署平台 Secret，不提交到 Git。

核心变量：

```env
LLM_PROVIDER=openai-compatible
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=
QWEATHER_API_KEY=
AMAP_API_KEY=
JWT_SECRET=change-me-in-production
```

## 验证

```powershell
$env:DATABASE_URL='postgresql+asyncpg://travel:travel@localhost:15432/travel'
$env:REDIS_URL='redis://localhost:16379'
.\server\.venv\Scripts\python.exe -m pytest server\tests -q
corepack pnpm build
```
