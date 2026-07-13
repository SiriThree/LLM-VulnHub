export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export type AnalysisRecord = {
  id: number;
  vulnerability_id: number;
  summary: string;
  risk_reason: string;
  suggested_fix: string;
  model_name: string;
  prompt_version: string;
  created_at: string;
};

export type VulnerabilityOccurrence = {
  id: number;
  intelligence_item_id?: number | null;
  intelligence_title?: string | null;
  intelligence_status?: string | null;
  source_url?: string | null;
  published_at?: string | null;
  evidence_excerpt: string;
  confidence: number;
  created_at: string;
  updated_at: string;
};

export type Vulnerability = {
  id: number;
  title: string;
  vuln_type: string;
  severity: string;
  score: number;
  affected_component: string;
  description: string;
  attack_method: string;
  impact: string;
  mitigation: string;
  source?: string | null;
  reference_url?: string | null;
  source_url?: string | null;
  confidence: number;
  status: string;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type VulnerabilityDetail = Vulnerability & {
  occurrences: VulnerabilityOccurrence[];
  analyses: AnalysisRecord[];
};

export type DataSource = {
  id: number;
  name: string;
  source_type: string;
  url: string;
  enabled: boolean;
  interval_minutes: number;
  last_collected_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type MergeCandidate = {
  id: number;
  intelligence_item_id: number;
  candidate_vulnerability_id: number;
  merge_score: number;
  merge_reason: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type IntelligenceItem = {
  id: number;
  source_id: number | null;
  collected_document_id: number | null;
  vulnerability_id: number | null;
  title: string;
  url?: string | null;
  raw_text: string;
  normalized_text: string;
  content_hash: string;
  language: string;
  triage_confidence: number;
  triage_category: string;
  triage_reason: string;
  extracted_data: Record<string, unknown>;
  review_notes?: string | null;
  status: string;
  collected_at: string;
  created_at: string;
  updated_at: string;
  merge_candidates: MergeCandidate[];
};

export type IntelligenceListResponse = {
  items: IntelligenceItem[];
};

export type IntelligenceStats = {
  total: number;
  pending_review: number;
  approved: number;
  rejected: number;
  triaged: number;
  high_risk_pending_review: number;
  merge_candidates_pending: number;
};

export type ReviewAction = {
  id: number;
  actor: string;
  target_type: string;
  target_id: number;
  action: string;
  before_snapshot: Record<string, unknown>;
  after_snapshot: Record<string, unknown>;
  reason: string;
  created_at: string;
};

export type ReviewActionListResponse = {
  items: ReviewAction[];
};

export type ReviewStats = {
  total_actions: number;
  approvals: number;
  rejections: number;
  merges: number;
  unique_actors: number;
  last_24h_actions: number;
  top_actors: Array<{ actor: string; count: number }>;
};

export type OpsMetrics = {
  queue_metrics: {
    queued: number;
    running: number;
    success: number;
    failed: number;
  };
  source_health: {
    total_sources: number;
    enabled_sources: number;
    disabled_sources: number;
    recently_failed_notifications: number;
  };
  provider_metrics: {
    analysis_jobs_total: number;
    avg_score: number;
    provider_distribution: Record<string, number>;
    severity_distribution: Record<string, number>;
  };
  llm_usage: {
    total_calls: number;
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
    avg_latency_ms: number;
    provider_distribution: Record<string, number>;
    model_distribution: Record<string, number>;
  };
  daily_trends: Array<{
    date: string;
    collected_documents: number;
    analysis_jobs: number;
    review_actions: number;
  }>;
};

export type SchedulerOverview = {
  beat_jobs: Array<{
    name: string;
    task: string;
    schedule_seconds: number;
  }>;
  sources: Array<{
    source_id: number;
    name: string;
    enabled: boolean;
    interval_minutes: number;
    last_collected_at?: string | null;
    next_run_at?: string | null;
    status: string;
  }>;
};

export type DeadLetterTask = {
  id: number;
  task_type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  dead_letter_reason?: string | null;
  current_stage?: string | null;
  error_message?: string | null;
  queue_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type PromptRegistryItem = {
  key: string;
  agent_name: string;
  version: string;
  required_keys: string[];
  usage_count: number;
  success_count: number;
  failure_count: number;
  avg_latency_ms: number;
};

export type EvalRun = {
  file_name: string;
  provider: string;
  dataset_size: number;
  triage_accuracy: number;
  triage_precision: number;
  triage_recall: number;
  extraction_completeness: number;
  merge_precision: number;
  generated_at: string;
};

export type NotificationEvent = {
  id: number;
  task_status: string;
  event_type: string;
  channel: string;
  severity: string;
  title: string;
  message: string;
  payload: Record<string, unknown>;
  source_id?: number | null;
  document_id?: number | null;
  intel_item_id?: number | null;
  analysis_job_id?: number | null;
  queue_name?: string | null;
  notified_at?: string | null;
  acknowledged: boolean;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  acknowledgment_note?: string | null;
  created_at: string;
  updated_at: string;
};

export type NotificationListResponse = {
  items: NotificationEvent[];
};

export type AgentExecution = {
  id: number;
  agent_name: string;
  stage_name: string;
  status: string;
  provider_name?: string | null;
  model_name?: string | null;
  prompt_version: string;
  retry_count: number;
  latency_ms?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

export type AnalysisJob = {
  id: number;
  pipeline_name: string;
  pipeline_version: string;
  status: string;
  source_url?: string | null;
  raw_text_hash: string;
  raw_text_excerpt: string;
  provider_name?: string | null;
  model_name?: string | null;
  relevance: Record<string, unknown>;
  extracted_fields: Record<string, unknown>;
  similar_snapshot: Array<Record<string, unknown>>;
  asset_impact_summary: string;
  asset_impact_details: Record<string, unknown>;
  score?: number | null;
  severity?: string | null;
  risk_reason: string;
  review_summary: string;
  report: string;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  agent_executions: AgentExecution[];
};

export type AnalyzeResult = {
  relevance: {
    is_ai_vulnerability: boolean;
    confidence: number;
    related_area: string;
    reason: string;
  };
  extracted: Partial<Vulnerability> & {
    tags?: string[];
    risk_reason?: string;
    review_summary?: string;
    asset_impact_summary?: string;
    asset_impact_details?: Record<string, unknown>;
    similar?: Vulnerability[];
  };
  vulnerability?: Vulnerability | null;
  report: string;
  analysis_job?: AnalysisJob | null;
};

export type CollectedDocument = {
  id: number;
  source_id: number | null;
  title: string;
  url?: string | null;
  raw_text: string;
  content_hash: string;
  is_ai_related: boolean;
  confidence: number;
  status: string;
  vulnerability_id?: number | null;
  collected_at: string;
};

export type PipelineEvent = {
  stage: string;
  status?: string;
  message: string;
  timestamp: string;
  source_id?: number;
  confidence?: number;
  document_id?: number;
  intel_item_id?: number;
};

export type SourceRun = {
  source_id: number;
  source_name: string;
  source_type: string;
  url: string;
  status: string;
  stage: string;
  discovered: number;
  processed: number;
  queued_analysis?: number;
  saved: number;
  duplicates: number;
  pending_review: number;
  ignored: number;
  failed: number;
  started_at?: string;
  finished_at?: string;
  elapsed_seconds?: number;
  error?: string;
  events: PipelineEvent[];
};

export type TaskMetrics = {
  discovered: number;
  processed: number;
  queued_analysis: number;
  analyzed: number;
  queued_review: number;
  notifications: number;
  saved: number;
  failed: number;
  duplicates: number;
  pending_review: number;
  ignored: number;
};

export type TaskRecord = {
  id: number;
  task_type: string;
  status: string;
  input_data: Record<string, unknown>;
  output_data: {
    pipeline?: string;
    trigger?: string;
    requested_source_id?: number | null;
    execution_mode?: string;
    queue_task_id?: string | null;
    queue_name?: string | null;
    attempt_count?: number;
    max_attempts?: number;
    started_at?: string | null;
    finished_at?: string | null;
    elapsed_seconds?: number | null;
    current_stage?: string;
    last_message?: string;
    dead_letter?: boolean;
    dead_letter_reason?: string | null;
    dead_letter_at?: string | null;
    stage_history?: PipelineEvent[];
    source_runs?: SourceRun[];
    metrics?: TaskMetrics;
    source_total?: number;
  };
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskListResponse = {
  items: TaskRecord[];
};

type ActorContext = {
  actor?: string;
  role?: string;
};

function parseCookieValue(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function readBrowserActorContext(): ActorContext {
  if (typeof document === "undefined") return {};
  const cookieMap = Object.fromEntries(
    document.cookie
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const [key, ...rest] = part.split("=");
        return [key, parseCookieValue(rest.join("="))];
      })
  );

  return {
    actor: cookieMap.llm_vulnhub_actor,
    role: cookieMap.llm_vulnhub_role,
  };
}

async function readServerActorContext(): Promise<ActorContext> {
  try {
    const headersModule = await import("next/headers");
    const store = await headersModule.cookies();
    return {
      actor: store.get("llm_vulnhub_actor")?.value,
      role: store.get("llm_vulnhub_role")?.value,
    };
  } catch {
    return {};
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const actorContext = typeof window === "undefined" ? await readServerActorContext() : readBrowserActorContext();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(actorContext.actor ? { "X-Actor": actorContext.actor } : {}),
      ...(actorContext.role ? { "X-Role": actorContext.role } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}
