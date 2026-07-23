# LLM-VulnHub

> 架构图、RAG 数据流、信任边界与 STRIDE 风险清单见 [`docs/Architecture-and-Threat-Model.md`](docs/Architecture-and-Threat-Model.md)。

LLM-VulnHub 是一个面向大语言模型应用安全的漏洞情报平台，用于把公开来源中的原始安全文本转化为可采集、可分析、可复核、可入库、可检索和可问答的 AI / LLM 漏洞资产。

当前平台覆盖的主流程：

```text
真实数据源采集 -> LLM 专项初筛 -> 多阶段 AI 分析 -> 情报池人工复核 -> 标准化入库 -> 漏洞库 / 看板 / RAG 问答
```

## 核心能力

- 动态采集：支持 GitHub Advisory、RSS、厂商公告、框架 Release Atom 等来源。
- LLM 漏洞初筛：过滤普通软件新闻、普通依赖 CVE、教程和无关发布公告，优先保留 LLM / RAG / Agent / 工具调用相关风险。
- AI 结构化抽取：抽取标题、漏洞类型、等级、评分、影响组件、攻击方式、影响、修复建议、标签和来源证据。
- 多阶段分析：保留 triage、extract、merge、risk、asset impact、review 等阶段的执行轨迹。
- 情报池复核：支持待人工复核、确认入库、驳回、合并候选处理和批量操作。
- 漏洞库管理：支持搜索、筛选、分页、详情查看、手动新增和编辑。
- RAG 智能问答：基于漏洞库资产进行多语言语义检索，返回带参考记录的可复核回答。
- 安全设计：在前端展示系统架构、信任边界、STRIDE 风险清单、RAG 专项控制与上线基线，数据由后端安全模型 API 统一提供。
- 运营监控：展示队列、调度器、数据源健康、任务状态、通知和 LLM 调用指标。
- 页面草稿保存：部分表单和 RAG 页面会自动保存临时草稿，切换页面后不会立即丢失输入。

## 技术栈

- 前端：Next.js 15、React、TypeScript、Tailwind CSS、lucide-react
- 后端：FastAPI、Pydantic、SQLAlchemy 2.0、Alembic
- 数据库：SQLite 本地开发，PostgreSQL + pgvector 用于 Docker 部署
- 异步任务：Celery + Redis
- AI 接口：统一 `LLMClient`，支持 DeepSeek、OpenAI、mock
- RAG 检索：FastEmbed + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 部署：Windows 本地脚本或 Docker Compose

## 目录结构

```text
.
├── backend/                 # FastAPI、Celery、AI workflow、RAG 服务
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── core/            # 配置
│   │   ├── db/              # SQLAlchemy 模型和会话
│   │   ├── schemas/         # Pydantic schema
│   │   ├── services/        # 采集、LLM、情报、漏洞、RAG、运维服务
│   │   └── workflows/       # 多阶段 AI 分析流程
│   └── alembic/             # 数据库迁移
├── frontend/                # Next.js 前端
├── scripts/                 # 本地启动/停止脚本
├── data/                    # 示例数据和种子资源
├── docs/                    # 设计和说明文档
└── docker-compose.yml
```

## 快速启动

推荐在 Windows 本地开发时使用脚本启动。Docker Compose 适合完整部署演示。

### 方式一：Windows 本地启动

前置要求：

- Python 3.12
- Node.js 20+
- Docker Desktop，用于启动 Redis
- 已配置根目录 `.env` 或 `backend/.env`

首次启动：

```powershell
cd D:\2025-2026-3
.\scripts\start-dev.ps1
```

依赖已经安装后，可以跳过安装：

```powershell
.\scripts\start-dev.ps1 -SkipInstall
```

默认访问地址：

- 前端：http://127.0.0.1:3000
- API 文档：http://127.0.0.1:8000/docs

停止所有后台进程：

```powershell
.\scripts\stop-dev.ps1
```

常见日志位置：

```text
backend/backend-dev.log
backend/celery-ingestion.log
backend/celery-analysis-1.log
backend/celery-analysis-2.log
backend/celery-review-notification.log
backend/celery-beat.log
frontend/frontend-dev.log
```

说明：

- Windows 下 Celery 使用 `solo` pool。脚本会启动多个 worker 进程来模拟并发。
- 如果你已经手动启动 Redis，可以使用 `.\scripts\start-dev.ps1 -SkipRedis`。
- `http://127.0.0.1:8000/` 返回 404 是正常的，后端根路径没有页面，请访问 `/docs`。

### 方式二：Docker Compose 启动

复制环境变量：

```powershell
copy .env.example .env
```

启动：

```powershell
docker compose up --build
```

`.env.example` 默认让 Docker 自动分配空闲的主机端口。启动后查询实际地址：

```powershell
docker compose port frontend 3000
docker compose port backend 8000
```

浏览器端通过前端的 `/api/v1` 同源代理访问后端，避免随机端口变化或跨域配置影响页面请求。

停止：

```powershell
docker compose down
```

清空容器数据卷：

```powershell
docker compose down -v
```

如果端口冲突，可以在 `.env` 中调整：

```env
FRONTEND_PORT=0
BACKEND_PORT=0
POSTGRES_PORT=0
REDIS_PORT=0
NEXT_PUBLIC_API_BASE=/api/v1
INTERNAL_API_BASE=http://backend:8000/api/v1
```

`0` 表示由 Docker 自动分配空闲主机端口；`INTERNAL_API_BASE` 始终使用容器网络中的 `backend:8000`。

## 手动启动

### 后端

```powershell
cd D:\2025-2026-3\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```powershell
cd D:\2025-2026-3\frontend
npm install
npm run dev -- -p 3000
```

如果页面显示成浏览器默认样式，通常是旧 Next.js 进程或 CSS 静态资源缓存异常。停止旧 Node 进程后重新启动前端，并在浏览器中按 `Ctrl + F5` 强制刷新。

### Redis

```powershell
cd D:\2025-2026-3
docker compose up -d redis
```

### Celery

```powershell
cd D:\2025-2026-3\backend

# 采集队列
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q ingestion --pool=solo --loglevel=info

# 分析队列，可启动多个窗口提升吞吐
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q analysis --pool=solo --loglevel=info

# 复核与通知队列
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q review,notification --pool=solo --loglevel=info

# 定时调度
.\.venv\Scripts\celery.exe -A app.worker.celery_app beat --loglevel=info
```

本地开发更推荐使用：

```powershell
.\scripts\start-dev.ps1 -SkipInstall
```

## 环境变量

根目录 `.env` 用于 Docker Compose；`backend/.env` 用于本地后端开发。常用配置如下：

```env
LLM_PROVIDER=deepseek

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

LLM_TIMEOUT_SECONDS=45
LLM_MAX_RETRIES=2
LLM_TEMPERATURE=0.1
LLM_FALLBACK_TO_MOCK=false

GITHUB_TOKEN=

DATABASE_URL=sqlite:///./llm_vulnhub.db
REDIS_URL=redis://localhost:6379/0

NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
INTERNAL_API_BASE=http://backend:8000/api/v1

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_CACHE_DIR=./.cache/fastembed
MODEL_DOWNLOAD_PROXY=
```

说明：

- `LLM_PROVIDER` 支持 `deepseek`、`openai`、`mock`。
- `GITHUB_TOKEN` 建议配置，否则 GitHub Advisory 匿名请求可能被限流。
- `LLM_FALLBACK_TO_MOCK=true` 时，模型不可用会退回 mock 文本，适合演示流程。
- `EMBEDDING_MODEL` 用于 RAG 语义检索，默认模型支持中英文。
- `MODEL_DOWNLOAD_PROXY` 可用于 Docker 构建阶段下载 embedding 模型，例如 `http://host.docker.internal:7897`。

## RAG 问答

RAG 模块使用两层召回策略：

1. 多语言 embedding 语义向量召回。
2. 关键词、标题、影响组件等字段加权排序。

回答生成时会遵循：

- 只基于召回到的漏洞库记录回答。
- 关键结论需要标注 `[1]`、`[2]` 等参考编号。
- 证据不足时明确说明不能从当前记录确认。
- 防护/缓解类问题按“主要风险、可执行措施、排查重点”组织。

首次切换 embedding 模型、导入旧数据库或发现 RAG 召回异常时，需要重建向量：

```powershell
cd D:\2025-2026-3\backend
.\.venv\Scripts\python.exe -m app.reindex_embeddings
```

Docker 环境中：

```powershell
docker compose exec backend python -m app.reindex_embeddings
```

示例问题：

- `RAG 数据泄露通常有哪些缓解措施？`
- `Prompt Injection 漏洞应该如何防护？`
- `哪些漏洞会影响 Agent 或工具调用链路？`

## 演示流程

### 1. 动态采集

1. 打开“动态采集”页面。
2. 查看待处理队列、最近采集结果和数据源健康状态。
3. 触发采集任务后，在任务中心观察 crawl、analysis、review 等阶段。
4. 对待处理文档执行“确认入库”或“去复核”。

### 2. 情报池复核

1. 打开“情报池”。
2. 查看待审核队列和右侧详情。
3. 根据 AI 判断、来源可信度、血缘链路和原始文本做复核。
4. 执行确认入库、驳回或合并候选处理。

### 3. 漏洞库

1. 打开“漏洞库”。
2. 使用搜索、筛选和分页浏览标准化漏洞记录。
3. 查看详情页中的来源、复核、分析记录和血缘信息。

### 4. RAG 问答

1. 确认漏洞库已有数据。
2. 打开“RAG 问答”。
3. 输入安全问题并调整召回数量。
4. 查看 AI 回答和右侧参考漏洞。

## 运维页面

“运行运营”页面用于查看：

- 队列中、运行中、成功任务、异常信号。
- 调度器任务和数据源调度状态。
- 数据源总数、启用数、停用数和失败通知数。
- 分析任务总数、平均风险评分、模型调用次数和平均延迟。
- 风险等级分布和 Token 用量。

当前布局已把数据源调度状态放到页面下方，核心指标和分析统计放在上方，便于快速扫描。

## 数据清理

如果要重新演示完整采集链路，可以清理业务数据但保留数据源配置。通常不要删除 `data_sources`。

可清理的业务表包括：

```text
agent_executions
analysis_jobs
merge_candidates
vulnerability_occurrences
intelligence_items
collected_documents
analysis_records
document_chunks
vulnerabilities
tags
review_actions
tasks
vulnerability_tags
```

## 关键代码入口

- 后端入口：`backend/app/main.py`
- 配置：`backend/app/core/config.py`
- Celery：`backend/app/worker.py`
- 动态采集：`backend/app/services/collector_service.py`
- 情报池：`backend/app/services/intel_service.py`
- 漏洞库：`backend/app/services/vulnerability_service.py`
- RAG 服务：`backend/app/services/rag_service.py`
- 安全模型服务：`backend/app/services/security_model_service.py`
- 安全模型 API：`backend/app/api/security_model.py`
- Embedding 服务：`backend/app/services/embedding_service.py`
- 向量重建：`backend/app/reindex_embeddings.py`
- LLM 封装：`backend/app/services/llm_service.py`
- AI 工作流：`backend/app/workflows/vuln_analysis_graph.py`
- RAG 前端：`frontend/app/rag-chat/page.tsx`
- 安全设计前端：`frontend/app/security-model/page.tsx`
- 情报池前端：`frontend/components/intel-pool-client.tsx`
- 草稿保存 hook：`frontend/lib/use-session-draft.ts`

## 常见问题

### 页面变成无样式 HTML

通常是旧 Next.js 进程还在运行，或者 CSS 静态资源 404。

处理方式：

1. 停止旧的 Node / Next.js 进程。
2. 重新运行 `npm run dev -- -p 3000`。
3. 浏览器按 `Ctrl + F5` 强制刷新。

### RAG 召回结果不相关

先重建 embedding：

```powershell
cd D:\2025-2026-3\backend
.\.venv\Scripts\python.exe -m app.reindex_embeddings
```

如果仍然异常，检查：

- 漏洞库是否已有足够相关记录。
- `EMBEDDING_MODEL` 是否一致。
- 旧数据库中的 `document_chunks` 是否已更新。

### Celery beat 报 `EOFError: Ran out of input`

通常是本地调度缓存损坏，删除后重启即可：

```powershell
Remove-Item backend\celerybeat-schedule.* -Force
```

### 采集成功但入库少

优先查看动态采集页的数据源健康指标：

- 请求成功率低：数据源或网络问题。
- 初筛通过率低：来源与 LLM 安全主题不够相关。
- LLM 命中率低：候选文本不是大模型漏洞。
- 入库转化率低：可能重复、字段不完整或需要人工复核。

### GitHub Advisory 限流

配置 `GITHUB_TOKEN`。公开 Advisory 读取场景通常只需要最小只读能力。
