const BROWSER_API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";
const SERVER_API_BASE = process.env.INTERNAL_API_BASE ?? "http://backend:8000/api/v1";

export const API_BASE = typeof window === "undefined" ? SERVER_API_BASE : BROWSER_API_BASE;

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

export type MergeCandidateExplanation = MergeCandidate & {
  candidate_title?: string | null;
  candidate_severity?: string | null;
  candidate_score?: number | null;
  candidate_component?: string | null;
  quality: string;
  match_signals: string[];
  review_hint: string;
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
  reviewable: number;
  pending_review: number;
  ignored: number;
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

export type EvalSample = {
  id: string;
  expected_ai: boolean;
  predicted_ai?: boolean | null;
  triage_correct?: boolean | null;
  confidence?: number | null;
  extraction_exact: Record<string, boolean>;
  extraction_completeness?: number | null;
  merge_correct?: boolean | null;
  errors: string[];
};

export type EvalDataset = {
  dataset_size: number;
  positive_samples: number;
  negative_samples: number;
  categories: Record<string, number>;
  samples: Array<{
    id: string;
    raw_text: string;
    expected: Record<string, unknown>;
  }>;
};

export type EvalRunDetail = EvalRun & {
  summary: Record<string, unknown>;
  samples: EvalSample[];
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
    merge_suggestions?: Record<string, unknown>;
  };
  vulnerability?: Vulnerability | null;
  report: string;
  analysis_job?: AnalysisJob | null;
};

export type ConfirmAnalysisResult = {
  vulnerability: Vulnerability;
  analysis_job: AnalysisJob;
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

export type CollectorRecentRun = {
  task_id: number;
  source_id?: number | null;
  source_name: string;
  source_type: string;
  status: string;
  stage: string;
  discovered: number;
  prefilter_passed: number;
  processed: number;
  queued_analysis: number;
  analyzed: number;
  ai_related: number;
  saved: number;
  duplicates: number;
  pending_review: number;
  ignored: number;
  failed: number;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_seconds?: number | null;
  error?: string | null;
};

export type SourceHealth = {
  source_id: number;
  name: string;
  source_type: string;
  enabled: boolean;
  interval_minutes: number;
  last_collected_at?: string | null;
  status: string;
  trust_score: number;
  trust_level: string;
  documents_total: number;
  ai_related_documents: number;
  pending_review_documents: number;
  stored_documents: number;
  duplicate_documents: number;
  recent_run_count: number;
  recent_failure_count: number;
  success_rate: number;
  request_success_rate: number;
  prefilter_pass_rate: number;
  llm_hit_rate: number;
  library_conversion_rate: number;
  recent_discovered: number;
  recent_prefilter_passed: number;
  recent_queued_analysis: number;
  recent_analyzed: number;
  recent_ai_related: number;
  recent_saved: number;
  freshness_minutes?: number | null;
  signals: string[];
};

export type CollectorOverview = {
  source_metrics: Record<string, number>;
  document_metrics: Record<string, number>;
  queue_metrics: Record<string, number>;
  source_health: SourceHealth[];
  recent_runs: CollectorRecentRun[];
  pending_documents: CollectedDocument[];
  recent_documents: CollectedDocument[];
};

export type IntelligenceLineage = {
  intelligence_item_id: number;
  title: string;
  status: string;
  triage_category: string;
  triage_confidence: number;
  source?: {
    id: number;
    name: string;
    source_type: string;
    url: string;
    enabled: boolean;
    interval_minutes: number;
    last_collected_at?: string | null;
    trust_score: number;
    trust_level: string;
    status: string;
    signals: string[];
  } | null;
  collected_document?: {
    id: number;
    title: string;
    url?: string | null;
    status: string;
    is_ai_related: boolean;
    confidence: number;
    collected_at: string;
    content_hash: string;
  } | null;
  linked_vulnerability?: {
    id: number;
    title: string;
    severity: string;
    score: number;
    status: string;
  } | null;
  merge_candidates: MergeCandidateExplanation[];
  review_actions: ReviewAction[];
  trace: Array<{
    stage: string;
    title: string;
    status: string;
    timestamp?: string | null;
    detail: string;
  }>;
};

export type VulnerabilityLineage = {
  vulnerability_id: number;
  title: string;
  severity: string;
  score: number;
  status: string;
  occurrences: Array<{
    occurrence_id: number;
    published_at?: string | null;
    confidence: number;
    evidence_excerpt: string;
    intelligence_item_id?: number | null;
    intelligence_title?: string | null;
    intelligence_status?: string | null;
    collected_document_id?: number | null;
    collected_document_title?: string | null;
    source_id?: number | null;
    source_name?: string | null;
    source_type?: string | null;
    source_trust_score?: number | null;
    source_trust_level?: string | null;
  }>;
  review_actions: Array<{
    id: number;
    actor: string;
    action: string;
    target_type: string;
    target_id: number;
    reason: string;
    created_at: string;
  }>;
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
