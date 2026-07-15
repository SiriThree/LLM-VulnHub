# LLM-VulnHub

面向 AI 大模型与 Agent 场景的漏洞情报采集、AI 分析、审核入库与检索问答平台。

项目核心目标是把“公开来源中的原始安全文本”变成“可审核、可追踪、可检索、可展示”的 AI 漏洞资产，覆盖动态采集、AI 相关性判断、结构化抽取、风险分析、相似检测、人工复核、标准化入库和前端展示的完整链路。

## 1. 项目定位

LLM-VulnHub 不是单纯的漏洞列表页，而是一套 AI 漏洞运营平台原型，重点解决三类问题：

1. 如何持续发现和汇聚 AI 相关安全情报。
2. 如何利用 LLM 把原始文本转换成结构化漏洞记录。
3. 如何让分析结果进入可审核、可发布、可检索的业务流程。

当前版本已经具备一条可运行的主流程：

`真实数据源采集 -> 情报池预筛选 -> AI 分析/多 Agent 研判 -> 人工复核 -> 发布入库 -> 漏洞看板/RAG 问答`

## 2. 当前能力

### 动态采集

- 支持从真实公开源抓取情报
- 当前已接入的来源类型包括：
  - GitHub Security Advisories
  - RSS / 安全博客 / 厂商公告类源
- 支持数据源管理、立即采集、任务追踪、失败重试
- 支持采集前预过滤，减少普通产品新闻、发布公告、教程文章进入分析链路

### AI 分析

- AI 相关性判断：判断文本是否属于 AI / LLM / Agent 安全情报
- AI 结构化抽取：抽取标题、漏洞类型、影响组件、攻击方式、影响、修复建议等字段
- AI 辅助风险解释：生成风险原因、资产影响说明、复核建议
- 相似漏洞候选推荐：为人工合并或去重提供参考
- 多 Agent 执行轨迹展示：前端可查看 triage / extract / merge / review 等阶段结果

### 业务流程

- 情报池：统一承接采集结果与 AI 分析结果
- 审核流转：支持 reviewable / ignored / approved 等状态
- 漏洞库：支持标准化漏洞记录的入库与展示
- 任务中心：展示 crawl / analyze_document / review 等异步任务状态
- 通知与运营看板：提供平台运行侧观察视图

### 前端展示

- Dashboard 漏洞态势看板
- 动态采集中心
- 情报池审核台
- AI 结构化抽取台
- 漏洞库列表与详情
- 任务中心
- RAG 问答页
- 平台设置页

## 3. 技术栈

### 前端

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui 风格组件

### 后端

- FastAPI
- Pydantic
- SQLAlchemy 2.0
- Alembic

### 数据与异步

- PostgreSQL
- pgvector
- Redis
- Celery

### AI / 工作流

- 统一 `LLMClient` 封装
- 支持 `DeepSeek / OpenAI / mock`
- LangGraph 风格的多阶段分析编排

### 部署

- Docker Compose

## 4. 目录结构

```text
.
├─ backend/                 # FastAPI + Celery + AI workflow
│  ├─ app/
│  │  ├─ api/               # 路由层
│  │  ├─ core/              # 配置与基础设施
│  │  ├─ db/                # 模型与会话
│  │  ├─ schemas/           # Pydantic schema
│  │  ├─ services/          # 采集、AI、评分、情报、漏洞等服务
│  │  ├─ workflows/         # LangGraph / 多阶段分析工作流
│  │  └─ evals/             # AI 评测脚本与数据集
│  └─ alembic/              # 数据库迁移
├─ frontend/                # Next.js 前端
├─ docs/                    # 2.0 设计文档、开发清单、评估指南
├─ scripts/                 # 辅助脚本
└─ docker-compose.yml
```

## 5. 核心流程

### 5.1 动态采集流程

1. 数据源定时或手动触发采集任务
2. 抓取原始条目并写入 `CollectedDocument`
3. 执行预过滤，剔除明显无关的普通资讯
4. 创建分析任务进入 AI 流程

### 5.2 AI 分析流程

1. `Triage Agent`
   - 判断是否属于 AI 安全情报
   - 输出分类与置信度
2. `Extraction Agent`
   - 抽取结构化漏洞字段
3. `Merge Agent`
   - 发现相似漏洞，给出去重/合并建议
4. `Risk / Asset / Reviewer Agent`
   - 补充风险解释、资产影响、发布建议
5. 写回情报池，等待人工复核或直接入库

### 5.3 审核与入库

1. 审核员在情报池查看 AI 分析结果
2. 对可发布记录执行批准
3. 平台将标准化结果写入漏洞库
4. 在 Dashboard、漏洞详情页、RAG 问答中对外提供使用

## 6. 本地启动

### 6.1 后端

```powershell
cd D:\2025-2026-3\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

接口文档：

- FastAPI OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

说明：

- `http://127.0.0.1:8000/` 返回 404 是正常的，后端没有首页路由。
- 健康检查建议访问 `/health` 或 `/docs`。

### 6.2 前端

```powershell
cd D:\2025-2026-3\frontend
npm install
npm run dev
```

前端地址：

- Web UI: [http://127.0.0.1:3000](http://127.0.0.1:3000)

### 6.3 Redis / Celery

如果需要完整体验异步采集与分析链路，需要额外启动 Redis 和 Celery worker。

Redis 启动后，再启动 worker：

```powershell
cd D:\2025-2026-3\backend
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker --loglevel=info
```

说明：

- 在 Windows 本地开发环境中，Celery 已按 `solo` 模式适配，避免 prefork 带来的兼容性问题。
- 如果 worker 没有消费任务，优先检查 Redis 是否启动，以及 worker 是否成功监听 `ingestion / analysis / review / notification` 队列。

### 6.4 Docker Compose

```powershell
cd D:\2025-2026-3
docker compose up --build
```

## 7. 环境变量

根目录 `.env` 需要按实际情况配置。

### LLM

使用 DeepSeek：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=your_key
```

使用 OpenAI：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4.1-mini
```

### GitHub Advisory

```env
GITHUB_TOKEN=your_token
```

未配置 `GITHUB_TOKEN` 时，匿名请求可能会被限流，导致采集速度慢或部分源失败。

## 8. 如何验证与演示

推荐按下面这条顺序演示：

### 路线 A：动态采集主线

1. 打开采集中心，查看真实数据源
2. 对某个数据源点击“立即采集”
3. 到任务中心观察：
   - crawl 任务是否从 `queued` 进入 `running`
   - 是否开始出现发现数、处理数、待分析数
4. 到情报池查看新进入的情报
5. 选择可复核项执行批准入库
6. 到漏洞库与 Dashboard 查看结果

### 路线 B：AI 抽取主线

1. 打开 `AI 结构化抽取`
2. 输入一段 AI 漏洞文本
3. 检查模型是否输出：
   - 标题
   - 漏洞类型
   - 严重等级 / 分数
   - 影响组件
   - 攻击方式
   - 修复建议
4. 观察 Phase 2 Agent 执行轨迹
5. 需要时手动修订后再入库

### 路线 C：检索问答主线

1. 漏洞库存在已发布记录后
2. 打开 RAG 问答页
3. 提问：
   - “LangChain 相关的提示词注入有哪些典型风险？”
   - “RAG 数据泄露漏洞通常怎么修复？”
4. 检查回答是否引用了平台内漏洞记录

## 9. 当前版本的边界

这一版已经能体现“真实来源 + AI 分析 + 审核入库 + 前端展示”的完整闭环，但它仍然是偏原型到工程化过渡阶段，不是完全面向生产的大规模平台。

当前已具备：

- 可运行的业务主流程
- 真实来源接入
- 异步任务与任务中心
- 多阶段 AI 分析
- 人工审核与发布

当前仍可继续加强：

- 更多高质量真实数据源
- 更强的去重与实体归一化
- 更稳定的并发吞吐与限流控制
- 更细的审核策略与告警策略
- 更完整的评测集与自动化回归测试

## 10. 重点代码入口

如果你要快速理解项目，建议优先看这些文件：

- 后端入口：[D:\2025-2026-3\backend\app\main.py](D:\2025-2026-3\backend\app\main.py)
- Celery worker：[D:\2025-2026-3\backend\app\worker.py](D:\2025-2026-3\backend\app\worker.py)
- 采集服务：[D:\2025-2026-3\backend\app\services\collector_service.py](D:\2025-2026-3\backend\app\services\collector_service.py)
- LLM 服务：[D:\2025-2026-3\backend\app\services\llm_service.py](D:\2025-2026-3\backend\app\services\llm_service.py)
- Prompt 注册表：[D:\2025-2026-3\backend\app\services\prompt_registry.py](D:\2025-2026-3\backend\app\services\prompt_registry.py)
- 情报池服务：[D:\2025-2026-3\backend\app\services\intel_service.py](D:\2025-2026-3\backend\app\services\intel_service.py)
- 风险评分：[D:\2025-2026-3\backend\app\services\scoring_service.py](D:\2025-2026-3\backend\app\services\scoring_service.py)
- 漏洞 Schema：[D:\2025-2026-3\backend\app\schemas\vulnerability.py](D:\2025-2026-3\backend\app\schemas\vulnerability.py)
- AI 抽取前端：[D:\2025-2026-3\frontend\components\ai-extract-client.tsx](D:\2025-2026-3\frontend\components\ai-extract-client.tsx)
- 情报池前端：[D:\2025-2026-3\frontend\components\intel-pool-client.tsx](D:\2025-2026-3\frontend\components\intel-pool-client.tsx)




