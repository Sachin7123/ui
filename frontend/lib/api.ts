export type TrendDirection = "up" | "down" | "steady";
export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type RunStatus =
  | "queued"
  | "running"
  | "degraded"
  | "paused"
  | "completed"
  | "failed";

export type MetricCard = {
  id: string;
  label: string;
  value: string;
  delta: string;
  direction: TrendDirection;
  hint: string;
};

export type TimePoint = {
  timestamp: string;
  value: number;
  run_id?: string | null;
  label?: string | null;
};

export type Series = {
  id: string;
  label: string;
  color: string;
  points: TimePoint[];
};

export type RunRecord = {
  run_id: string;
  name: string;
  model_name: string;
  trainer: string;
  source: string;
  status: RunStatus;
  started_at: string;
  updated_at: string;
  current_step: number;
  total_steps: number;
  progress: number;
  throughput_tokens_per_sec: number;
  gpu_utilization: number;
  reward_latest: number;
  loss_latest: number;
  success_rate: number;
  anomaly_score: number;
  last_alert?: string | null;
  tags: string[];
};

export type EventRecord = {
  event_id: string;
  run_id: string;
  event_type: string;
  severity: Severity;
  timestamp: string;
  message: string;
  payload: Record<string, unknown>;
};

export type PromptRecord = {
  prompt_id: string;
  run_id: string;
  step: number;
  timestamp: string;
  scenario: string;
  input_text: string;
  metadata: Record<string, unknown>;
};

export type OutputRecord = {
  output_id: string;
  run_id: string;
  prompt_id: string;
  step: number;
  timestamp: string;
  output_text: string;
  label: string;
  score: number;
  metadata: Record<string, unknown>;
};

export type RewardRecord = {
  reward_id: string;
  run_id: string;
  step: number;
  timestamp: string;
  reward_total: number;
  components: Record<string, number>;
};

export type AlertRecord = {
  alert_id: string;
  run_id: string;
  alert_type: string;
  severity: Severity;
  timestamp: string;
  title: string;
  detail: string;
  resolved: boolean;
  confidence: number;
};

export type RepairRecord = {
  repair_id: string;
  run_id: string;
  scenario_id: string;
  timestamp: string;
  failed_request: Record<string, unknown>;
  repair_reasoning: string;
  healed_request?: Record<string, unknown> | null;
  retry_result: string;
  confidence: number;
  outcome: "success" | "failed" | "abstained";
  safe_abstained: boolean;
};

export type FailureCauseRow = {
  name: string;
  count: number;
  severity: Severity;
};

export type TrainingInspectorRow = {
  prompt: PromptRecord;
  output: OutputRecord;
  reward?: RewardRecord | null;
};

export type PipelineOverviewResponse = {
  headline: string;
  tagline: string;
  stats: MetricCard[];
  active_runs: RunRecord[];
  reward_series: Series[];
  loss_series: Series[];
  throughput_series: Series[];
  recent_events: EventRecord[];
  system_health: MetricCard;
};

export type CommandCenterResponse = {
  generated_at: string;
  stats: MetricCard[];
  active_runs: RunRecord[];
  reward_series: Series[];
  loss_series: Series[];
  throughput_series: Series[];
  gpu_series: Series[];
  logs: EventRecord[];
  alerts: AlertRecord[];
  repairs: RepairRecord[];
};

export type HistoricalAnalyticsResponse = {
  stats: MetricCard[];
  reward_trends: Series[];
  loss_trends: Series[];
  throughput_trends: Series[];
  best_runs: RunRecord[];
  failure_causes: FailureCauseRow[];
  alerts: AlertRecord[];
};

export type InspectorResponse = {
  stats: MetricCard[];
  examples: TrainingInspectorRow[];
  prompt_series: Series[];
};

export type AlertsResponse = {
  stats: MetricCard[];
  alerts: AlertRecord[];
  events: EventRecord[];
};

export type RemorphEngineResponse = {
  stats: MetricCard[];
  repairs: RepairRecord[];
  recent_events: EventRecord[];
};

export type PageResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type EventPayload<T = Record<string, unknown>> = {
  channel: string;
  event_type: string;
  timestamp: string;
  data: T;
};

export type SystemHealthResponse = {
  generated_at: string;
  ingest_rate_per_sec: number;
  stream_rate_per_sec: number;
  storage_latency_ms: number;
  active_run_count: number;
  queue_depth: number;
  alerts_open: number;
};

export type OpenEnvMetaResponse = {
  name: string;
  environment_ready: boolean;
  import_error: string | null;
  submission_path: string | null;
  description: string;
};

export type OpenEnvStepResponse = {
  observation: Record<string, unknown>;
  reward: number;
  done: boolean;
  info: Record<string, unknown>;
};

function getApiBaseUrl(): string {
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBase) {
    return configuredBase.replace(/\/+$/, "");
  }

  if (process.env.NODE_ENV === "development") {
    return "http://127.0.0.1:8000";
  }

  return "";
}

function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(buildApiUrl(path), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchJsonPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed: ${response.status} ${text}`);
  }
  return (await response.json()) as T;
}

export type StreamEventHandlers<T> = {
  onMessage: (payload: EventPayload<T>) => void;
  onOpen?: () => void;
  onError?: () => void;
};

export function streamEvents<T>(
  path: string,
  handlerOrCallback:
    | StreamEventHandlers<T>
    | ((payload: EventPayload<T>) => void),
): () => void {
  const handlers: StreamEventHandlers<T> =
    typeof handlerOrCallback === "function"
      ? { onMessage: handlerOrCallback }
      : handlerOrCallback;
  const source = new EventSource(buildApiUrl(path));
  source.onmessage = (event) => {
    handlers.onMessage(JSON.parse(event.data) as EventPayload<T>);
  };
  source.onopen = () => {
    handlers.onOpen?.();
  };
  source.onerror = () => {
    handlers.onError?.();
  };
  return () => source.close();
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatTimestamp(value: string): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}
