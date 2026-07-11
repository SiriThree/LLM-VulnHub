# LLM-VulnHub

面向 AI 大模型应用的漏洞库管理与智能分析系统。项目根据设计文档实现了动态漏洞采集、AI 相关性判断、结构化抽取、规则风险评分、相似漏洞检测、标准化入库、RAG 问答、漏洞管理和前端展示。

## 技术栈

- 前端：Next.js + TypeScript + Tailwind CSS + shadcn/ui 风格组件
- 后端：FastAPI + Pydantic + SQLAlchemy 2.0 + Alembic
- 数据库：PostgreSQL + pgvector，默认本地开发也支持 SQLite
- AI 工作流：LangGraph 设计口径，当前以可测试 workflow 节点实现
- 异步任务：Celery + Redis
- 模型接口：统一 `LLMClient`，支持 `mock`、OpenAI、DeepSeek
- 部署：Docker Compose

## 快速启动

本地后端开发：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
```

前端开发：

```powershell
cd frontend
npm install
npm run dev
```

Docker Compose：

```powershell
docker compose up --build
```

访问：

- 前端：http://localhost:3000
- 后端 OpenAPI：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 演示主线

1. 打开 Dashboard 查看漏洞统计。
2. 进入动态采集中心，添加 `local_file` 数据源：`/data/sample_sources.json`，点击立即采集。
3. 系统自动完成 AI 相关性判断、结构化抽取、评分、入库。
4. 进入 AI 抽取页，粘贴 Prompt Injection 或 RAG 泄露文本，确认字段后入库。
5. 进入 RAG 问答页，询问防护方式，查看回答和引用漏洞。

## 模型配置

默认 `LLM_PROVIDER=mock`，不需要 API Key，也能完成课程演示。接入真实模型时设置：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

或：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
```

统一入口在 `backend/app/services/llm_service.py`。

如果要稳定采集 GitHub Advisory 源，建议额外配置：

```env
GITHUB_TOKEN=...
```

未配置时，RSS 和本地演示源可正常工作；GitHub Advisory 源在匿名限流下会被自动跳过并记录错误信息。
