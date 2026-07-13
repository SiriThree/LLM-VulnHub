# LLM-VulnHub 2.0 Design Report

## 1. Project Positioning

### 1.1 Background
LLM-VulnHub 1.0 has completed a runnable prototype for AI vulnerability collection, AI relevance judgment, structured extraction, vulnerability storage, dashboard display, and RAG-based Q&A. The current version already forms a basic technical loop:

`external source -> text collection -> AI relevance judgment -> structured extraction -> scoring -> storage -> search / display / Q&A`

However, version 1.0 still has two obvious limitations:

1. It is stronger in technical demonstration than in business workflow closure.
2. It is stronger in single-flow processing than in platform-level orchestration and governance.

Therefore, version 2.0 is intended to upgrade the system from a runnable prototype into a more complete platform-level AI vulnerability intelligence and risk operations system.

### 1.2 New Positioning
LLM-VulnHub 2.0 is positioned as:

**An AI vulnerability intelligence analysis and risk operations platform for LLM / Agent / RAG applications.**

Its core value is no longer limited to “collect and store vulnerabilities,” but extends to:

- continuous external intelligence ingestion
- AI / multi-agent semantic understanding
- event merging and review
- enterprise asset impact analysis
- intelligent vulnerability knowledge services
- operational visibility and task governance

### 1.3 Target Users

Primary users:

- AI security operations engineers
- enterprise AI application security teams
- internal red team / risk control teams
- platform-side vulnerability intelligence analysts

Secondary users:

- AI application developers
- architects responsible for LLM / RAG / Agent systems
- management roles who need weekly security summary and risk visibility

---

## 2. Product Goals

### 2.1 Business Goals
Build a platform that can continuously ingest external AI vulnerability intelligence, automatically transform raw text into structured vulnerability knowledge, correlate it with internal assets, and support review, operations, search, and Q&A workflows.

### 2.2 Technical Goals

1. Upgrade from single pipeline processing to modular workflow orchestration.
2. Upgrade from direct-to-storage flow to intelligence-pool + review + publish flow.
3. Upgrade from simple duplicate avoidance to event merge and occurrence tracking.
4. Upgrade from rule + database system to AI + vector retrieval + workflow platform.
5. Upgrade from local prototype tasks to production-oriented asynchronous task architecture.

### 2.3 Resume / Interview Value Goals
The 2.0 version should be strong enough to be presented as:

- an AI application engineering project
- a multi-agent workflow system
- a production-oriented asynchronous backend platform
- an enterprise AI risk management system

---

## 3. Scope of 2.0

### 3.1 In Scope

1. Multi-source dynamic ingestion
2. Raw intelligence pool
3. Multi-agent AI analysis pipeline
4. Vulnerability merge / master record model
5. Review workflow and state machine
6. Enterprise asset impact analysis
7. RAG knowledge service
8. Observability and task governance

### 3.2 Out of Scope for Initial 2.0 Delivery

1. SSO / full enterprise IAM
2. multi-tenant isolation
3. mobile client
4. full commercial alerting integrations
5. strict HA / distributed transaction guarantees

These can be listed as later roadmap items.

---

## 4. Core Functional Architecture

### 4.1 Module Overview

LLM-VulnHub 2.0 is designed around eight major functional modules:

1. Source Ingestion Center
2. Raw Intelligence Pool
3. Multi-Agent Analysis Workflow
4. Vulnerability Merge and Master Record System
5. Asset Impact Management
6. Review and Operations Workbench
7. Knowledge Retrieval and RAG Q&A
8. Notification and Reporting Center

### 4.2 End-to-End Business Flow

The complete business flow is:

`source registration -> scheduled collection -> raw intelligence pool -> AI triage -> field extraction -> merge candidate generation -> review -> publish -> asset impact match -> RAG / report / alert`

Expanded flow:

1. External sources continuously generate new security-related texts.
2. Ingestion jobs fetch and normalize raw documents.
3. Raw texts enter the intelligence pool instead of going straight into the vulnerability library.
4. AI / Agent workflow evaluates whether the text is AI-vulnerability related.
5. If relevant, the extraction agent produces structured vulnerability fields.
6. The merge agent compares the candidate with existing master vulnerabilities.
7. The review console allows analysts to approve, reject, or merge candidates.
8. Approved items become published vulnerability records.
9. Asset impact service maps vulnerabilities to internal AI assets.
10. RAG service and reporting service reuse the published vulnerability knowledge.

---

## 5. Detailed Functional Design

### 5.1 Source Ingestion Center

#### Goals

- continuously ingest external AI vulnerability intelligence
- support configurable source schedules
- retain original texts and metadata
- support re-collection and traceability

#### Supported Source Types

- GitHub Security Advisories
- RSS / Atom feeds
- NVD / CVE feeds
- official framework release feeds
- security blogs
- manual text submission
- manual URL submission

#### Core Features

- source registration and editing
- polling interval configuration
- enable / disable control
- source status monitoring
- incremental cursor storage
- rate limiting
- retry and failure recording

#### Example Source Metadata

- source name
- source type
- source URL
- polling interval
- last cursor / last fetched timestamp
- enabled flag
- status

---

### 5.2 Raw Intelligence Pool

#### Why This Module Exists
Version 1.0 sends collected texts directly toward storage. That is convenient for a demo, but weak for real operations.

Version 2.0 introduces an intelligence pool as a buffer layer between raw collection and published vulnerabilities.

#### Core Capabilities

- store all collected documents before publishing
- keep raw text, metadata, source trace, language, and timestamps
- allow manual and automated triage
- support non-vulnerability and low-confidence rejection

#### Intelligence States

- `new`
- `triaged`
- `extracted`
- `merge_candidate`
- `pending_review`
- `approved`
- `rejected`
- `archived`

#### Benefits

- makes the platform operational instead of purely automatic
- preserves evidence chain
- enables auditing and debugging of AI decisions

---

### 5.3 Multi-Agent Analysis Workflow

#### Why Multi-Agent Is Introduced
Version 1.0 mainly uses a single AI pipeline. That is sufficient for a simple prototype.  
Version 2.0 introduces multiple agents because the platform now needs different cognitive roles:

- triage
- extraction
- merge
- impact analysis
- review assistance

These roles have different goals, prompts, tools, and evaluation metrics.

#### Proposed Agent Roles

##### 1. Source Triage Agent
Input:
- raw intelligence text
- source metadata

Output:
- whether the text is AI-vulnerability related
- confidence score
- rough category
- triage reason

##### 2. Vulnerability Extraction Agent
Input:
- text judged relevant

Output:
- title
- vulnerability type
- affected component
- attack path
- impact
- mitigation
- tags
- possible version scope

##### 3. Merge Agent
Input:
- extracted vulnerability candidate
- similar existing records

Output:
- new record / merge into existing / uncertain
- merge reason
- candidate master record

##### 4. Risk Explanation Agent
Input:
- extracted fields
- scoring factors

Output:
- human-readable explanation
- analyst summary
- remediation priority suggestion

##### 5. Asset Impact Agent
Input:
- published vulnerability
- asset inventory
- framework / dependency inventory

Output:
- affected assets
- confidence
- internal severity adjustment suggestion

##### 6. Reviewer Agent
Input:
- extraction result
- merge result
- source evidence

Output:
- quality check flags
- missing field warnings
- inconsistency hints

#### Workflow Engine
LangGraph remains appropriate in 2.0 because the workflow is no longer a simple linear chain. It now includes:

- conditional routing
- specialist roles
- possible retry and review loops
- tool calls
- explicit state passing

Suggested execution graph:

`ingest -> triage agent -> extract agent -> merge agent -> reviewer agent -> score / explain -> impact agent -> persist -> notify`

---

### 5.4 Vulnerability Merge and Master Record System

#### Problem in 1.0
Multiple external sources about the same vulnerability may produce multiple database entries. This weakens operational value.

#### 2.0 Solution
Introduce a master record model:

- one `master vulnerability`
- many `occurrences`
- many `source evidences`
- one merge history

#### Core Concepts

##### Master Record
Represents the logical vulnerability event.

##### Occurrence
Represents one piece of source intelligence referring to the event.

##### Merge Candidate
Represents an AI- or rules-generated possible link between a new item and an existing master record.

#### Benefits

- reduces duplicate records
- creates better timeline and evidence trace
- supports source correlation and confidence accumulation

---

### 5.5 Asset Impact Management

#### Why This Matters
Without asset correlation, the platform is mainly a public vulnerability library.
With asset correlation, it becomes an internal AI risk management platform.

#### Core Concepts

- `asset`
- `asset component`
- `framework stack`
- `model service`
- `rag service`
- `agent service`

#### Example Assets

- internal LangChain agent service
- enterprise RAG assistant
- tool orchestration gateway
- model routing gateway
- embedding generation pipeline

#### Core Capabilities

- register internal AI assets
- maintain component inventory
- map vulnerabilities to components
- derive affected asset list
- compute internal business priority

#### Why This Is Valuable
It turns:
- “there is a new Prompt Injection issue in the ecosystem”

into:
- “this issue may affect our internal document assistant and tool gateway”

That is a much stronger business outcome.

---

### 5.6 Review and Operations Workbench

#### Core Use Cases

- review AI extraction results
- compare source evidence
- merge duplicate vulnerability candidates
- edit fields before publishing
- reject invalid intelligence
- track audit trail

#### Status Flow for Published Vulnerabilities

- `draft`
- `review_pending`
- `approved`
- `published`
- `suppressed`
- `resolved`

#### Review Console Design

Suggested layout:

- left: source text and evidence
- middle: extracted structured fields
- right: similar records, merge suggestions, asset impact hints

#### Review Actions

- approve as new vulnerability
- merge into existing master record
- reject
- request re-analysis
- edit fields

---

### 5.7 RAG Knowledge and Q&A

#### 1.0 Capability
Basic vulnerability-library Q&A.

#### 2.0 Upgrade
Make RAG serve operational and internal risk analysis scenarios.

#### Query Types

- by vulnerability type
- by framework
- by asset
- by time window
- by severity
- by remediation pattern

#### Example Questions

- Which high-risk Agent vulnerabilities appeared in the last 7 days?
- Does any recent Prompt Injection issue affect our LangChain-based services?
- What are the common mitigation patterns for RAG data leakage?

#### Retrieval Layers

1. vector similarity
2. metadata filtering
3. asset-aware context assembly

---

### 5.8 Notification and Reporting

#### Notification Use Cases

- high-risk newly approved vulnerability
- high-risk vulnerability affecting internal assets
- backlog in review queue
- source ingestion failure summary

#### Report Types

- daily vulnerability digest
- weekly risk summary
- asset impact report
- false positive / review quality report

---

## 6. System Architecture Design

### 6.1 Suggested 2.0 Service Layout

The recommended architecture is modular within one repository initially, with a later path toward service separation.

#### Service Blocks

1. `frontend-console`
2. `platform-api`
3. `ingestion-service`
4. `analysis-service`
5. `kb-service`
6. `worker-system`

### 6.2 Responsibilities

#### frontend-console
- intelligence pool UI
- vulnerability management UI
- review workbench
- asset risk UI
- task center
- RAG console

#### platform-api
- business APIs
- workflow control APIs
- review APIs
- vulnerability APIs
- asset APIs

#### ingestion-service
- polling
- parsing
- source cursor tracking
- raw intelligence persistence

#### analysis-service
- LLM calls
- agent orchestration
- field extraction
- merge analysis
- impact analysis

#### kb-service
- embedding generation
- vector retrieval
- RAG context builder

#### worker-system
- asynchronous execution
- scheduled jobs
- retry management

---

## 7. Data Model Design

### 7.1 Key Tables

#### `intel_sources`
Source registry.

#### `intel_items`
Raw intelligence documents.

Suggested fields:
- id
- source_id
- title
- url
- raw_text
- normalized_text
- language
- published_at
- collected_at
- content_hash
- status

#### `analysis_jobs`
Every analysis stage execution.

Suggested fields:
- id
- intel_item_id
- stage
- agent_name
- status
- input_ref
- output_ref
- retry_count
- latency_ms
- model_name
- token_usage_prompt
- token_usage_completion
- error_message

#### `vulnerability_records`
Master vulnerabilities.

#### `vulnerability_occurrences`
Source-linked occurrences.

#### `merge_candidates`
Potential merge links.

#### `assets`
Enterprise AI assets.

#### `asset_components`
Asset dependency / component mapping.

#### `asset_vulnerability_impacts`
Impact relationships.

#### `review_actions`
Audit and review history.

#### `notifications`
Alert and digest records.

---

## 8. Workflow and State Machine Design

### 8.1 Intelligence Lifecycle

`new -> triaged -> extracted -> merge_candidate -> pending_review -> approved/rejected -> archived`

### 8.2 Vulnerability Lifecycle

`draft -> review_pending -> approved -> published -> suppressed/resolved`

### 8.3 Task Lifecycle

`queued -> running -> success/failed/retrying`

Task stages:

- collect
- parse
- triage
- extract
- merge
- review_hint
- impact_match
- persist
- notify

---

## 9. AI / LLM Design

### 9.1 Core AI Functions

The 2.0 version uses AI for:

1. relevance classification
2. structured information extraction
3. merge suggestion
4. remediation explanation
5. review assistance
6. RAG answer generation

### 9.2 What Is Not Treated as Core AI
Pure rule scoring should not be overstated as an AI feature.
It can remain part of the platform but should be described as:

**rule-driven risk evaluation based on AI-extracted semantics**

### 9.3 Prompt and Workflow Governance

Add:

- prompt registry
- prompt version
- schema version
- workflow version
- evaluation dataset

This is important for production AI engineering maturity.

---

## 10. Engineering Design

### 10.1 Observability

Add:

- structured logs
- tracing
- metrics
- task latency dashboard
- token / cost tracking
- success / failure rate tracking

### 10.2 Reliability

Add:

- retry with backoff
- dead letter queue
- idempotent task handling
- source cursor checkpoint
- source rate limiting
- circuit breaker for provider failure

### 10.3 Security

Add:

- role-based access control
- audit logging
- secret management
- schema validation for model outputs
- prompt injection and output guardrails

### 10.4 Testing

Testing layers:

- unit tests
- integration tests
- workflow tests
- prompt regression tests
- provider integration tests
- sample-based extraction evaluation

---

## 11. Frontend Design

### 11.1 New Pages

1. Intelligence Pool
2. Review Workbench
3. Master Vulnerability Detail
4. Asset Risk Dashboard
5. Operations Metrics Dashboard
6. Notification Center

### 11.2 UX Principles

- operator-first workflows
- evidence visible before decision
- master record and occurrences clearly separated
- asset impact visible in vulnerability detail
- task execution visible in pipeline view

---

## 12. Roadmap

### Phase 1: Business Workflow Upgrade

- intelligence pool
- review workflow
- master vulnerability record
- merge candidates

### Phase 2: AI / Agent Upgrade

- multiple agents
- reviewer agent
- merge agent
- prompt / workflow versioning
- evaluation datasets

### Phase 3: Engineering Upgrade

- stronger async execution
- observability
- retry / rate limit / cursor
- cost tracking

### Phase 4: Enterprise Risk Upgrade

- asset inventory
- impact mapping
- alerts and reports
- internal risk views

---

## 13. Expected Outcomes

After 2.0 is completed, the system should be able to claim:

1. Continuous multi-source AI vulnerability intelligence ingestion
2. AI / multi-agent assisted understanding and extraction
3. Merge-aware, reviewable vulnerability knowledge production
4. Enterprise asset impact analysis
5. RAG-based knowledge service
6. Production-style asynchronous workflow governance

In resume or interview language, the project becomes:

**an AI vulnerability intelligence and risk operations platform with multi-agent analysis workflow and production-oriented backend architecture**

