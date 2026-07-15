# LLM-VulnHub

LLM-VulnHub 是一个面向大语言模型应用安全的漏洞情报采集、AI 分析、审核入库与 RAG 问答平台原型。项目目标是把公开来源中的原始安全文本，转换成可追踪、可审核、可检索、可展示的 AI 大模型漏洞资产。

当前系统覆盖的主流程：

```text
真实数据源采集 -> LLM 专项初筛 -> AI 多阶段分析 -> 情报池审核 -> 标准化入库 -> 漏洞看板 / RAG 问答
```

## 核心能力

- 动态采集：支持 GitHub Advisory、RSS、厂商公告、框架 Release Atom 等真实来源。
- 定向漏洞源：默认启用 LangChain、LlamaIndex、Transformers、Gradio、vLLM、ChromaDB、MCP SDK、n8n-MCP 等 LLM 组件定向 Advisory 源。
- LLM 专项初筛：先过滤普通 npm/pip CVE、产品新闻、教程、发布公告，再进入 AI 分析。
- AI 结构化抽取：抽取标题、漏洞类型、影响组件、攻击方式、影响、修复建议、风险分数等字段。
- 多阶段 Agent 分析：包含 triage、extract、merge、risk、asset impact、review 等阶段，并保留执行轨迹。
- 相似漏洞检测：给出候选合并项，辅助去重和人工复核。
- 情报池审核：支持 ignored、pending_review、approved 等状态流转。
- 漏洞库管理：支持标准化漏洞记录的增删改查、详情、搜索与筛选。
- RAG 问答：基于平台内漏洞资产进行检索问答。
- 任务中心：展示 crawl、analysis、review、notification、beat 等异步任务状态。
- 源健康指标：展示请求成功率、初筛通过率、LLM 命中率、入库转化率。

## 技术栈

- 前端：Next.js、TypeScript、Tailwind CSS、shadcn/ui 风格组件
- 后端：FastAPI、Pydantic、SQLAlchemy 2.0、Alembic
- 数据库：PostgreSQL + pgvector，开发环境也支持 SQLite
- 异步任务：Celery + Redis
- AI 工作流：LangGraph 风格多阶段工作流
- 模型接口：统一 `LLMClient`，支持 DeepSeek、OpenAI、mock
- 部署：Docker Compose

## 目录结构

```text
.
├── backend/                 # FastAPI + Celery + AI workflow
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── core/            # 配置与安全
│   │   ├── db/              # SQLAlchemy 模型与会话
│   │   ├── schemas/         # Pydantic schema
│   │   ├── services/        # 采集、LLM、情报、漏洞、评分等服务
│   │   └── workflows/       # 多阶段 AI 分析工作流
│   └── alembic/             # 数据库迁移
├── frontend/                # Next.js 前端
├── docs/                    # 设计报告、开发清单、演示文档
├── scripts/                 # 本地启动、报告生成等脚本
├── data/                    # 示例数据与辅助资源
└── docker-compose.yml
```

## 快速启动

推荐两种方式：

- 本地开发演示：使用 `scripts/start-dev.ps1`，适合 Windows 本机调试。
- Docker 一键运行：使用 `docker compose up --build`，适合完整部署演示。

### 方式一：Windows 本地一键启动

前置要求：

- Python 3.12
- Node.js 20+
- Docker Desktop，用于启动 Redis
- 已配置 `.env` 或 `backend/.env`

首次启动：

```powershell
cd D:\2025-2026-3
.\scripts\start-dev.ps1
```

再次启动，如果依赖已经装好，可以跳过安装：

```powershell
.\scripts\start-dev.ps1 -SkipInstall
```

默认会在后台启动：

```text
Redis
FastAPI backend
Next.js frontend
Celery ingestion worker
Celery analysis worker x 2
Celery review/notification worker
Celery beat
```

访问地址：

- 前端：http://127.0.0.1:3000
- API 文档：http://127.0.0.1:8000/docs

停止所有后台进程：

```powershell
.\scripts\stop-dev.ps1
```

日志位置：

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

- Windows 下 Celery 使用 `solo` pool。为了体现并发，脚本会启动多个独立 worker 进程，而不是让你手动打开多个终端。
- 如果你已经自己启动 Redis，可以使用 `.\scripts\start-dev.ps1 -SkipRedis`。
- `http://127.0.0.1:8000/` 返回 404 是正常的，后端没有根页面，请访问 `/docs`。

### 方式二：Docker Compose 一键运行

复制并修改环境变量：

```powershell
copy .env.example .env
```

启动：

```powershell
docker compose up --build
```

访问：

- 前端：http://127.0.0.1:3000
- API 文档：http://127.0.0.1:8000/docs

停止：

```powershell
docker compose down
```

清空容器数据卷：

```powershell
docker compose down -v
```

## 手动启动方式

如果需要逐个服务调试，可以按下面方式启动。

### 后端

```powershell
cd D:\2025-2026-3\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 前端

```powershell
cd D:\2025-2026-3\frontend
npm install
npm run dev
```

### Redis

```powershell
cd D:\2025-2026-3
docker compose up -d redis
```

### Celery

如果手动启动，建议按队列拆分 worker：

```powershell
cd D:\2025-2026-3\backend

# 采集队列
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q ingestion --pool=solo --loglevel=info

# 分析队列，可以开两个窗口提高吞吐
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q analysis --pool=solo --loglevel=info

# 复核与通知队列
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q review,notification --pool=solo --loglevel=info

# 定时调度
.\.venv\Scripts\celery.exe -A app.worker.celery_app beat --loglevel=info
```

本地开发时更推荐使用：

```powershell
.\scripts\start-dev.ps1 -SkipInstall
```

## 环境变量

根目录 `.env` 用于 Docker Compose，`backend/.env` 用于本地后端开发。常用配置如下：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_key

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

GITHUB_TOKEN=your_token

DATABASE_URL=sqlite:///./llm_vulnhub.db
REDIS_URL=redis://localhost:6379/0
```

说明：

- `GITHUB_TOKEN` 建议配置，否则 GitHub Advisory 匿名请求可能限流。
- DeepSeek / OpenAI 二选一即可。
- 如果只是看流程，可以使用 `LLM_PROVIDER=mock`，但 AI 抽取真实性会下降。

## 演示流程

### 1. 动态采集

1. 打开“动态采集”页面。
2. 点击“采集全部启用源”。
3. 在任务中心观察 crawl 任务、source run 漏斗和 analysis 队列。
4. 回到采集页查看每个源的：
   - 请求成功率
   - 初筛通过率
   - LLM 命中率
   - 入库转化率
5. 到漏洞看板查看新增漏洞资产。

### 2. AI 结构化抽取

1. 打开“AI 抽取”页面。
2. 输入一段 LLM / RAG / Agent 漏洞文本。
3. 点击 AI 解析。
4. 查看结构化字段和 Phase 2 Agent 执行轨迹。

### 3. 情报池审核

1. 打开“情报池”。
2. 查看 ignored、pending_review、approved 状态。
3. 对可发布情报执行批准入库或合并处理。

### 4. RAG 问答

1. 确认漏洞库已有数据。
2. 打开“RAG 问答”。
3. 提问示例：
   - `LangChain 相关漏洞有哪些典型风险？`
   - `MCP 工具调用类漏洞如何修复？`
   - `RAG 数据泄露通常有哪些缓解措施？`

## 数据清理

如果需要重新演示完整采集链路，可以清空业务数据，保留数据源配置。建议通过后端脚本或数据库管理工具删除以下业务表：

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

不要删除 `data_sources`，否则需要重新 seed 数据源。

## 关键代码入口

- 后端入口：`backend/app/main.py`
- Celery 配置：`backend/app/worker.py`
- 动态采集：`backend/app/services/collector_service.py`
- 源健康指标：`backend/app/services/provenance_service.py`
- 情报池：`backend/app/services/intel_service.py`
- LLM 封装：`backend/app/services/llm_service.py`
- Prompt 注册：`backend/app/services/prompt_registry.py`
- AI 工作流：`backend/app/workflows/vuln_analysis_graph.py`
- 前端采集页：`frontend/app/collectors/page.tsx`
- AI 抽取前端：`frontend/components/ai-extract-client.tsx`
- 情报池前端：`frontend/components/intel-pool-client.tsx`

## 当前边界

当前版本已经可以展示完整闭环，但仍属于原型到工程化之间的阶段：

- 本地 Windows Celery 依赖多进程模拟并发，生产建议使用 Linux/Docker worker。
- 自动入库策略偏保守，仍需要人工复核能力兜底。
- 数据源虽然已聚焦 LLM 组件，但还可以继续扩展 NVD、OSV、厂商安全公告等来源。
- RAG 问答页和前端交互仍可进一步优化。

## 常见问题

### Celery beat 报 `EOFError: Ran out of input`

通常是 `backend/celerybeat-schedule.*` 本地调度缓存损坏，删除后重启即可：

```powershell
Remove-Item backend\celerybeat-schedule.* -Force
```

### 采集成功但入库少

先看采集页源级漏斗：

- 请求成功率低：数据源或网络问题。
- 初筛通过率低：源质量偏低，不是 LLM 安全源。
- LLM 命中率低：候选不是大模型漏洞。
- 入库转化率低：可能重复、字段不完整或需要人工复核。

### GitHub Advisory 限流

配置 `GITHUB_TOKEN`。Fine-grained token 不需要写权限，公开 Advisory 读取场景通常只需要最小只读能力。
