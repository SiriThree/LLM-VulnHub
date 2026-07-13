# LLM-VulnHub 2.0 Development Checklist

## 1. Goal of This Checklist

This checklist is intended to turn the 2.0 design into an executable implementation plan.  
It is organized by phase, module, data model, backend, frontend, AI workflow, and engineering requirements.

Each task is written in a way that can be used directly as a development backlog.

---

## 2. Delivery Principles

### 2.1 General Principles

- keep the 1.0 system runnable while iterating
- prefer additive evolution over disruptive rewrite in the early phase
- separate business entities before separating services
- build evaluation and observability together with AI functions
- do not introduce multi-agent orchestration before the review and merge business flow exists

### 2.2 Recommended Milestone Sequence

1. business workflow foundation
2. AI / multi-agent foundation
3. engineering hardening
4. enterprise asset and alerting layer

---

## 3. Phase 1 - Business Workflow Upgrade

### 3.1 Target

Upgrade from “collect -> analyze -> store” to:

`collect -> intelligence pool -> extract -> merge candidate -> review -> publish`

### 3.2 Database Tasks

#### Must Add Tables

- [x] create `intel_items`
- [x] create `vulnerability_occurrences`
- [x] create `merge_candidates`
- [x] create `review_actions`

#### Suggested Fields for `intel_items`

- [ ] `id`
- [ ] `source_id`
- [ ] `title`
- [ ] `url`
- [ ] `raw_text`
- [ ] `normalized_text`
- [ ] `content_hash`
- [ ] `language`
- [ ] `published_at`
- [ ] `collected_at`
- [ ] `status`
- [ ] `triage_confidence`
- [ ] `triage_category`

#### Suggested Fields for `vulnerability_occurrences`

- [ ] `id`
- [ ] `vulnerability_id`
- [ ] `intel_item_id`
- [ ] `source_url`
- [ ] `published_at`
- [ ] `evidence_excerpt`
- [ ] `confidence`

#### Suggested Fields for `merge_candidates`

- [ ] `id`
- [ ] `intel_item_id`
- [ ] `candidate_vulnerability_id`
- [ ] `merge_score`
- [ ] `merge_reason`
- [ ] `status`

#### Suggested Fields for `review_actions`

- [ ] `id`
- [ ] `actor`
- [ ] `target_type`
- [ ] `target_id`
- [ ] `action`
- [ ] `before_snapshot`
- [ ] `after_snapshot`
- [ ] `reason`
- [ ] `created_at`

### 3.3 Backend Tasks

#### Intelligence Pool APIs

- [x] add `GET /intel-items`
- [x] add `GET /intel-items/{id}`
- [ ] add `POST /intel-items/{id}/triage`
- [ ] add `POST /intel-items/{id}/extract`
- [x] add `POST /intel-items/{id}/reject`

#### Merge and Review APIs

- [x] add `GET /merge-candidates`
- [x] add `POST /merge-candidates/{id}/approve-merge`
- [ ] add `POST /merge-candidates/{id}/reject-merge`
- [x] add `POST /intel-items/{id}/publish`
- [ ] add `POST /intel-items/{id}/request-review`

#### Service Layer Tasks

- [x] refactor collector flow to store raw items first
- [x] stop direct publish from collector path
- [x] split “collect” from “publish”
- [x] add review audit logging

### 3.4 Frontend Tasks

#### Intelligence Pool Page

- [x] create `/intel-pool`
- [x] table with source, title, time, confidence, status
- [ ] filter by status
- [ ] filter by source type
- [ ] filter by confidence range
- [x] intelligence detail drawer / detail page

#### Review Workbench

- [ ] create `/review`
- [ ] three-column layout:
  - evidence text
  - extracted fields
  - merge suggestions
- [ ] approve button
- [ ] reject button
- [ ] merge button
- [ ] edit fields before publish

### 3.5 Acceptance Criteria

- [x] raw collected items no longer go directly to published vulnerability records
- [x] analysts can review and publish manually
- [x] merge candidates are visible before publish
- [x] audit trail exists for review actions

---

## 4. Phase 2 - AI / Agent Upgrade

### 4.1 Target

Upgrade from single AI workflow to role-based multi-agent workflow.

### 4.2 AI Role Definition Tasks

- [x] define `Triage Agent`
- [x] define `Extraction Agent`
- [x] define `Merge Agent`
- [x] define `Risk Explanation Agent`
- [x] define `Reviewer Agent`
- [x] define `Asset Impact Agent`

### 4.3 LangGraph / Workflow Tasks

- [x] redesign current workflow graph
- [x] add agent-specific nodes
- [x] add conditional routing after triage
- [x] add merge decision branch
- [x] add reviewer agent branch
- [ ] add retry / fallback node for invalid outputs

### 4.4 Prompt Governance Tasks

- [x] create prompt registry
- [x] create prompt version field
- [x] separate prompts by agent role
- [x] add output JSON schema contract
- [x] add invalid JSON retry strategy

### 4.5 Evaluation Tasks

- [x] build labeled triage dataset
- [x] build labeled extraction dataset
- [x] define triage accuracy metric
- [x] define extraction field completeness metric
- [x] define merge precision metric
- [x] compare mock / DeepSeek / OpenAI outputs

### 4.6 Backend Tasks

- [x] add `analysis_jobs` table
- [x] store each agent execution separately
- [x] store model name, latency, token usage, retry count
- [x] persist agent outputs and intermediate states

### 4.7 Acceptance Criteria

- [x] each AI step has a named role
- [x] failures can be localized to one stage
- [x] prompts are no longer mixed together in one generic chain
- [x] evaluation data exists for at least triage and extraction

---

## 5. Phase 3 - Engineering Hardening

### 5.1 Target

Upgrade from demo-style async behavior to production-oriented task processing.

### 5.2 Async Execution Tasks

- [x] separate ingestion tasks from analysis tasks
- [ ] separate review helper tasks from publish tasks
- [x] add retry with backoff
- [ ] add dead-letter handling
- [ ] add idempotent reprocessing protection
- [ ] add source cursor persistence

### 5.3 Queue / Event Tasks

#### Minimal Version

- [x] keep Celery + Redis but split queues by task type
- [x] define queue names:
  - ingestion
  - analysis
  - review
  - notification

#### Stronger Version

- [ ] evaluate migration path to Kafka / Redis Streams
- [ ] define domain events
- [ ] design event payload schemas

### 5.4 Observability Tasks

- [x] structured logs for all jobs
- [x] metrics for stage latency
- [ ] metrics for source success / failure
- [ ] metrics for AI provider latency
- [ ] metrics for token cost
- [ ] trace collection flow end-to-end

### 5.5 Reliability Tasks

- [ ] source rate limit controls
- [x] provider timeout handling
- [ ] provider fallback strategy
- [ ] task timeout guard
- [ ] duplicate task suppression

### 5.6 Acceptance Criteria

- [x] each stage has measurable latency
- [ ] source failures do not block other sources
- [x] retries are visible in task center
- [ ] repeat execution does not create duplicate published records

---

## 6. Phase 4 - Enterprise Asset and Risk Operations

### 6.1 Target

Upgrade from public vulnerability platform to enterprise AI risk management platform.

### 6.2 Database Tasks

- [ ] create `assets`
- [ ] create `asset_components`
- [ ] create `asset_vulnerability_impacts`
- [ ] create `notifications`

### 6.3 Asset Management Tasks

- [ ] add asset CRUD APIs
- [ ] add component registration per asset
- [ ] add framework / dependency mapping
- [ ] support asset tags: agent / rag / gateway / embedding / eval

### 6.4 Impact Analysis Tasks

- [ ] build component match rules
- [ ] add asset impact agent
- [ ] compute impact confidence
- [ ] store impact links
- [ ] show affected assets in vulnerability detail

### 6.5 Notification Tasks

- [ ] create daily digest generator
- [ ] create weekly summary generator
- [ ] create high-risk asset-impact alert rule
- [ ] create review backlog warning rule

### 6.6 Frontend Tasks

- [ ] create `/assets`
- [ ] create `/assets/[id]`
- [ ] create vulnerability impact section
- [ ] create notification center page
- [ ] create operations metrics page

### 6.7 Acceptance Criteria

- [ ] vulnerabilities can be mapped to internal assets
- [ ] high-risk impacted assets can be listed
- [ ] at least one summary report type is generated automatically

---

## 7. Cross-Cutting Backend Refactor Checklist

### 7.1 Module Refactor

- [ ] split `collector_service` into:
  - source ingestion service
  - raw intel persistence service
  - orchestration trigger service
- [ ] split `llm_service` into:
  - provider adapter
  - prompt registry
  - output validation helper
- [ ] split workflow package into:
  - triage workflow
  - extraction workflow
  - merge workflow
  - review workflow

### 7.2 API Refactor

- [ ] separate routes by bounded context:
  - sources
  - intel
  - analysis
  - review
  - vulnerabilities
  - assets
  - notifications

### 7.3 Schema Refactor

- [ ] add dedicated DTOs for:
  - intelligence items
  - merge candidates
  - review actions
  - asset impacts
  - notifications

---

## 8. Cross-Cutting Frontend Refactor Checklist

### 8.1 Frontend Information Architecture

- [ ] group navigation into:
  - Overview
  - Intelligence
  - Review
  - Vulnerabilities
  - Assets
  - Knowledge
  - Tasks
  - Settings

### 8.2 Component Tasks

- [ ] reusable evidence viewer
- [ ] reusable merge candidate card
- [ ] reusable asset impact table
- [ ] reusable stage timeline
- [ ] reusable AI analysis diagnostics panel

### 8.3 UX Improvement Tasks

- [ ] add row-level actions in intel pool
- [ ] add bulk actions for review queue
- [ ] add merge preview
- [ ] add approval confirmation modal
- [ ] add reviewer notes input

---

## 9. Testing Checklist

### 9.1 Unit Tests

- [ ] source parsing
- [ ] cursor logic
- [ ] scoring logic
- [ ] merge heuristics
- [ ] asset match rules

### 9.2 Integration Tests

- [ ] collect -> raw intel pool
- [ ] triage -> extraction
- [ ] extraction -> merge candidate
- [ ] review -> publish
- [ ] publish -> RAG retrieval

### 9.3 AI Regression Tests

- [ ] triage false-positive cases
- [ ] triage true-positive cases
- [ ] extraction field consistency cases
- [ ] merge correctness cases

### 9.4 Frontend Tests

- [ ] intelligence pool happy path
- [ ] review workbench happy path
- [ ] asset impact page loading
- [ ] task center polling

---

## 10. Documentation Checklist

- [ ] update README for 2.0 positioning
- [ ] add architecture diagram
- [ ] add data flow diagram
- [ ] document task state machine
- [ ] document AI / Agent role responsibilities
- [ ] document evaluation method
- [ ] document deployment modes

---

## 11. Recommended Implementation Order

If implementation bandwidth is limited, use this order:

### Step 1
- [ ] raw intelligence pool
- [ ] review workflow
- [ ] merge candidate model

### Step 2
- [ ] master record + occurrences
- [ ] review console
- [ ] publish flow

### Step 3
- [ ] multi-agent workflow
- [ ] analysis_jobs
- [ ] prompt / workflow versioning

### Step 4
- [ ] observability
- [ ] retries
- [ ] queue split

### Step 5
- [ ] asset registry
- [ ] impact mapping
- [ ] alerts / reports

---

## 12. Resume-Oriented Completion Markers

The project becomes resume-strong when the following are true:

- [ ] no longer direct-ingests into final vulnerability table
- [ ] has intelligence pool and review loop
- [ ] has merge-aware vulnerability knowledge model
- [ ] has multi-agent analysis roles
- [ ] has evaluation and observability
- [ ] has asset impact management
- [ ] has RAG-based security knowledge reuse

At that point, it can credibly be described as:

**a multi-agent AI vulnerability intelligence and risk operations platform with production-oriented asynchronous backend architecture**
