# AI Travel Agent Platform

多 Agent 智能旅行决策平台。工业级 Agent 系统架构，支持 DAG 编排、Memory 系统、RAG 检索、SSE 流式输出。

## Architecture

```
travel/
├── src/                    React + Vite + TypeScript 前端 (Leaflet 地图 + SSE 客户端)
├── server/                 FastAPI 后端 (Agent Runtime + BFF)
│   ├── app/
│   │   ├── main.py         FastAPI 入口
│   │   ├── api/            REST + SSE 端点
│   │   ├── agents/         Agent 定义 (prompts/ 目录管理)
│   │   ├── core/           Agent Runtime 核心 (Registry, DAG Executor, SSE)
│   │   ├── memory/         Memory 系统 (ShortTerm/LongTerm/RunMemory)
│   │   ├── tools/          Tool Registry + 工具实现
│   │   ├── workflows/      DAG 工作流定义
│   │   ├── schemas/        Pydantic 模型
│   │   ├── services/       业务服务层
│   │   └── db/             SQLAlchemy 模型 + 数据库连接
│   └── tests/
├── docker/
│   ├── postgres-pgvector/
│   └── redis/
├── docker-compose.yml
└── docs/
```

## Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Zustand, Leaflet
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy/SQLModel, Alembic
- **Database**: PostgreSQL 16 + pgvector (vector search for Memory + RAG)
- **Cache**: Redis 7 (short-term memory, session, rate limiting)
- **AI**: OpenAI-compatible API (阿里云 DashScope / Qwen)
- **Testing**: pytest + pytest-asyncio (backend), Vitest (frontend)
- **Deploy**: Docker Compose, GitHub Actions

## Agent System

### Agent Runtime

自研轻量 Agent Runtime:
- **Agent Registry**: 插件化 Agent 注册与发现
- **Tool Registry**: 工具注册, schema 校验, timeout, retry
- **DAG Executor**: 拓扑排序 → 并行层并行执行 → 串行层串行执行
- **Memory Manager**: ShortTerm (Redis) + LongTerm (pgvector) + RunMemory
- **SSE Emitter**: 实时事件流 (run.created → step.started → tool.called → agent.completed)

### Agent List (10 Agents)

| Agent | 职责 | Phase |
|-------|------|-------|
| IntentAgent | 解析用户需求 | Phase 1 |
| MemoryAgent | 读取短期/长期记忆 | Phase 1 |
| WeatherAgent | 天气查询 + 风险分析 | Phase 1 |
| BudgetAgent | 预算分配 + 超支检测 | Phase 1 |
| CriticAgent | 方案审查 + Replan | Phase 1 |
| TrafficAgent | 交通方案 | Phase 2 |
| HotelAgent | 住宿推荐 | Phase 2 |
| FoodAgent | 美食推荐 | Phase 2 |
| AttractionAgent | 景点详情 | Phase 2 |
| ItineraryOptimizerAgent | 路线优化 | Phase 2 |

### DAG Execution Model

```
IntentAgent
  ├── MemoryAgent
  ├── WeatherAgent      ─┐
  ├── TrafficAgent       ├── 并行层
  ├── HotelAgent         │
  ├── FoodAgent         ─┘
  └── AttractionAgent
        ↓
  BudgetAgent             ── 串行层
        ↓
  ItineraryOptimizerAgent
        ↓
  CriticAgent
        ↓
  Planner / Replan
```

### Memory System

- **ShortTermMemory** (Redis): 当前对话上下文, TTL 自动过期
- **LongTermMemory** (pgvector): 用户长期偏好, 向量检索, 带 confidence
- **RunMemory** (PostgreSQL): 本次执行 trace, 工具结果, 失败原因

### SSE Event Types

`run.created → plan.generated → step.started → tool.called → tool.completed → memory.hit → agent.completed → critic.issued → replan.started → run.completed → run.failed`

## Getting Started

```bash
# Start infrastructure
docker-compose up -d postgres redis

# Backend
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
pnpm dev
```

## Environment Variables

```
DATABASE_URL=postgresql+asyncpg://travel:travel@localhost:5432/travel
REDIS_URL=redis://localhost:6379
QWEATHER_API_KEY=
DASHSCOPE_API_KEY=
JWT_SECRET=
EMBEDDING_MODEL=text-embedding-v3
CHAT_MODEL=qwen-plus
```

## Testing

```bash
# Backend
cd server && pytest -v

# Frontend
pnpm test
```

## Git Workflow

- Feature branches from `main`
- Conventional commits
- PR review before merge
- CI: lint → test → type-check → build
