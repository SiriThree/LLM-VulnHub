export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

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
    attempt_count?: number;
    max_attempts?: number;
    started_at?: string | null;
    finished_at?: string | null;
    elapsed_seconds?: number | null;
    current_stage?: string;
    last_message?: string;
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

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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
