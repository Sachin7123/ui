from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["info", "low", "medium", "high", "critical"]
RunStatus = Literal["queued", "running", "degraded", "paused", "completed", "failed"]
TrendDirection = Literal["up", "down", "steady"]
AlertType = Literal[
    "reward_drop",
    "loss_spike",
    "stalled_run",
    "bad_generation",
    "mode_collapse",
    "repair_regression",
]
RepairOutcome = Literal["success", "failed", "abstained"]


class MetricCard(BaseModel):
    id: str
    label: str
    value: str
    delta: str
    direction: TrendDirection
    hint: str


class TimePoint(BaseModel):
    timestamp: str
    value: float
    run_id: str | None = None
    label: str | None = None


class Series(BaseModel):
    id: str
    label: str
    color: str
    points: list[TimePoint]


class EventPayload(BaseModel):
    channel: str
    event_type: str
    timestamp: str
    data: dict[str, Any]


class RunRecord(BaseModel):
    run_id: str
    name: str
    model_name: str
    trainer: str
    source: str
    status: RunStatus
    started_at: str
    updated_at: str
    current_step: int
    total_steps: int
    progress: float = Field(ge=0.0, le=1.0)
    throughput_tokens_per_sec: float
    gpu_utilization: float = Field(ge=0.0, le=100.0)
    reward_latest: float
    loss_latest: float
    success_rate: float = Field(ge=0.0, le=1.0)
    anomaly_score: float = Field(ge=0.0, le=1.0)
    last_alert: str | None = None
    tags: list[str] = Field(default_factory=list)


class MetricSample(BaseModel):
    metric_id: str
    run_id: str
    metric_name: str
    split: str
    step: int
    timestamp: str
    value: float


class EventRecord(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    severity: Severity
    timestamp: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PromptRecord(BaseModel):
    prompt_id: str
    run_id: str
    step: int
    timestamp: str
    scenario: str
    input_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutputRecord(BaseModel):
    output_id: str
    run_id: str
    prompt_id: str
    step: int
    timestamp: str
    output_text: str
    label: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RewardRecord(BaseModel):
    reward_id: str
    run_id: str
    step: int
    timestamp: str
    reward_total: float
    components: dict[str, float] = Field(default_factory=dict)


class AlertRecord(BaseModel):
    alert_id: str
    run_id: str
    alert_type: AlertType
    severity: Severity
    timestamp: str
    title: str
    detail: str
    resolved: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RepairRecord(BaseModel):
    repair_id: str
    run_id: str
    scenario_id: str
    timestamp: str
    failed_request: dict[str, Any]
    repair_reasoning: str
    healed_request: dict[str, Any] | None = None
    retry_result: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    outcome: RepairOutcome
    safe_abstained: bool = False


class TrainingInspectorRow(BaseModel):
    prompt: PromptRecord
    output: OutputRecord
    reward: RewardRecord | None = None


class FailureCauseRow(BaseModel):
    name: str
    count: int
    severity: Severity


class PipelineOverviewResponse(BaseModel):
    headline: str
    tagline: str
    stats: list[MetricCard]
    active_runs: list[RunRecord]
    reward_series: list[Series]
    loss_series: list[Series]
    throughput_series: list[Series]
    recent_events: list[EventRecord]
    system_health: MetricCard


class HistoricalAnalyticsResponse(BaseModel):
    stats: list[MetricCard]
    reward_trends: list[Series]
    loss_trends: list[Series]
    throughput_trends: list[Series]
    best_runs: list[RunRecord]
    failure_causes: list[FailureCauseRow]
    alerts: list[AlertRecord]


class InspectorResponse(BaseModel):
    stats: list[MetricCard]
    examples: list[TrainingInspectorRow]
    prompt_series: list[Series]


class AlertsResponse(BaseModel):
    stats: list[MetricCard]
    alerts: list[AlertRecord]
    events: list[EventRecord]


class RemorphEngineResponse(BaseModel):
    stats: list[MetricCard]
    repairs: list[RepairRecord]
    recent_events: list[EventRecord]


class CommandCenterResponse(BaseModel):
    generated_at: str
    stats: list[MetricCard]
    active_runs: list[RunRecord]
    reward_series: list[Series]
    loss_series: list[Series]
    throughput_series: list[Series]
    gpu_series: list[Series]
    logs: list[EventRecord]
    alerts: list[AlertRecord]
    repairs: list[RepairRecord]


class PageResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class IngestMetricsRequest(BaseModel):
    items: list[MetricSample]


class IngestEventsRequest(BaseModel):
    items: list[EventRecord]


class IngestPromptsRequest(BaseModel):
    items: list[PromptRecord]


class IngestOutputsRequest(BaseModel):
    items: list[OutputRecord]


class IngestRewardsRequest(BaseModel):
    items: list[RewardRecord]


class IngestRepairsRequest(BaseModel):
    items: list[RepairRecord]


class SystemHealthResponse(BaseModel):
    generated_at: str
    ingest_rate_per_sec: float
    stream_rate_per_sec: float
    storage_latency_ms: float
    active_run_count: int
    queue_depth: int
    alerts_open: int
