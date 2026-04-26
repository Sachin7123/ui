from __future__ import annotations

import asyncio
import json
import math
import os
import queue
import random
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.models import (
    AlertRecord,
    AlertsResponse,
    CommandCenterResponse,
    EventPayload,
    EventRecord,
    FailureCauseRow,
    HistoricalAnalyticsResponse,
    IngestEventsRequest,
    IngestMetricsRequest,
    IngestOutputsRequest,
    IngestPromptsRequest,
    IngestRepairsRequest,
    IngestRewardsRequest,
    InspectorResponse,
    MetricCard,
    MetricSample,
    OutputRecord,
    PageResponse,
    PipelineOverviewResponse,
    PromptRecord,
    RepairRecord,
    RewardRecord,
    RemorphEngineResponse,
    RunRecord,
    Series,
    SystemHealthResponse,
    TimePoint,
    TrainingInspectorRow,
)
from app.repositories.artifacts import ArtifactRepository
from app.repositories.storage_factory import build_storage_backend
from app.repositories.storage_types import StorageBackend


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


@dataclass
class SimRun:
    run_id: str
    slot: int
    name: str
    model_name: str
    trainer: str
    source: str
    started_at: str
    total_steps: int
    current_step: int = 0
    reward_latest: float = 0.1
    loss_latest: float = 1.8
    success_rate: float = 0.35
    throughput: float = 920.0
    gpu_util: float = 64.0
    anomaly_score: float = 0.08
    status: str = "running"
    last_alert: str | None = None
    tags: list[str] | None = None


class StreamHub:
    def __init__(self) -> None:
        self._listeners: dict[str, set[queue.Queue[EventPayload]]] = defaultdict(set)
        self._lock = threading.Lock()

    def subscribe(self, channel: str) -> queue.Queue[EventPayload]:
        channel_queue: queue.Queue[EventPayload] = queue.Queue(maxsize=256)
        with self._lock:
            self._listeners[channel].add(channel_queue)
        return channel_queue

    def unsubscribe(
        self, channel: str, channel_queue: queue.Queue[EventPayload]
    ) -> None:
        with self._lock:
            self._listeners[channel].discard(channel_queue)

    def publish(self, channel: str, payload: EventPayload) -> int:
        with self._lock:
            listeners = list(self._listeners[channel])
        delivered = 0
        for listener in listeners:
            try:
                listener.put_nowait(payload)
                delivered += 1
            except queue.Full:
                continue
        return delivered

    def queue_depth(self) -> int:
        with self._lock:
            return sum(
                listener.qsize()
                for listeners in self._listeners.values()
                for listener in listeners
            )


class DemoService:
    def __init__(
        self,
        storage: StorageBackend | None = None,
        artifact_repo: ArtifactRepository | None = None,
    ) -> None:
        self._storage = storage or build_storage_backend()
        self._artifact_repo = artifact_repo or ArtifactRepository()
        self._data_source_mode = (
            os.getenv("DATA_SOURCE_MODE", "simulator").strip().lower()
        )
        self._hub = StreamHub()
        self._rng = random.Random(42)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._ingest_timestamps: deque[float] = deque(maxlen=6000)
        self._publish_timestamps: deque[float] = deque(maxlen=6000)
        self._storage_latency_ms: deque[float] = deque(maxlen=300)
        self._runs: dict[str, SimRun] = {}
        self._round_robin = 0
        self._artifact_cursor = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if self._data_source_mode in {"openenv", "artifacts", "artifact"}:
            self._bootstrap_from_openenv_artifacts()
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._artifact_stream_loop, daemon=True
            )
            self._thread.start()
            return

        self._seed_runs()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._simulate_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def subscribe(self, channel: str) -> queue.Queue[EventPayload]:
        return self._hub.subscribe(channel)

    def unsubscribe(
        self, channel: str, channel_queue: queue.Queue[EventPayload]
    ) -> None:
        self._hub.unsubscribe(channel, channel_queue)

    def pipeline_overview(self) -> PipelineOverviewResponse:
        active_runs = self._current_runs(limit=6)
        return PipelineOverviewResponse(
            headline="Real-time AI training observability for every ReMorph learning event.",
            tagline="Storage, streaming, anomaly detection, and API repair reasoning in one control plane.",
            stats=self._overview_cards(active_runs),
            active_runs=active_runs,
            reward_series=self._build_metric_series(
                "reward", "Reward", ["#38bdf8", "#8b5cf6", "#14b8a6"]
            ),
            loss_series=self._build_metric_series(
                "loss", "Loss", ["#fb7185", "#f59e0b", "#e879f9"]
            ),
            throughput_series=self._build_metric_series(
                "throughput", "Tokens/sec", ["#22c55e", "#2dd4bf", "#60a5fa"]
            ),
            recent_events=self._storage.recent_events(limit=8),
            system_health=MetricCard(
                id="system-health",
                label="System Health",
                value="Nominal",
                delta=f"{self.system_health().stream_rate_per_sec:.1f} ev/s",
                direction="steady",
                hint="Realtime API and pipeline storage are both active.",
            ),
        )

    def command_center(self) -> CommandCenterResponse:
        runs = self._current_runs(limit=6)
        return CommandCenterResponse(
            generated_at=iso_now(),
            stats=self._overview_cards(runs),
            active_runs=runs,
            reward_series=self._build_metric_series(
                "reward", "Reward", ["#38bdf8", "#8b5cf6", "#14b8a6"], limit=90
            ),
            loss_series=self._build_metric_series(
                "loss", "Loss", ["#fb7185", "#f59e0b", "#e879f9"], limit=90
            ),
            throughput_series=self._build_metric_series(
                "throughput", "Tokens/sec", ["#22c55e", "#2dd4bf", "#60a5fa"], limit=90
            ),
            gpu_series=self._build_metric_series(
                "gpu_utilization", "GPU %", ["#f59e0b", "#38bdf8", "#8b5cf6"], limit=90
            ),
            logs=self._storage.recent_events(limit=12),
            alerts=self._storage.recent_alerts(limit=6),
            repairs=self._storage.recent_repairs(limit=6),
        )

    def list_runs(self, *, page: int, page_size: int) -> PageResponse:
        runs = self._current_runs(limit=100)
        return self._paginate(runs, page=page, page_size=page_size)

    def historical_analytics(self) -> HistoricalAnalyticsResponse:
        runs = self._current_runs(limit=12)
        alerts = self._storage.recent_alerts(limit=10)
        causes = self._failure_causes(alerts)
        best_runs = sorted(
            runs, key=lambda item: (item.success_rate, item.reward_latest), reverse=True
        )[:4]
        return HistoricalAnalyticsResponse(
            stats=[
                MetricCard(
                    id="best-checkpoint",
                    label="Best Checkpoint Reward",
                    value=f"{best_runs[0].reward_latest:.2f}" if best_runs else "0.00",
                    delta=f"{len(best_runs)} tracked runs",
                    direction="up",
                    hint="Computed from persisted run snapshots.",
                ),
                MetricCard(
                    id="historical-alerts",
                    label="Historical Alerts",
                    value=str(self._storage.count("alerts")),
                    delta=f"{self._storage.count_open_alerts()} open",
                    direction="down",
                    hint="Stored in SQLite and replayable from JSONL.",
                ),
                MetricCard(
                    id="prompt-captures",
                    label="Prompt Captures",
                    value=str(self._storage.count("prompts")),
                    delta=f"{self._storage.count('outputs')} outputs",
                    direction="up",
                    hint="Inspector records accumulated over live simulation.",
                ),
                MetricCard(
                    id="repair-events",
                    label="Repair Events",
                    value=str(self._storage.count("repairs")),
                    delta="ReMorph-linked telemetry",
                    direction="steady",
                    hint="Shows API healing behavior alongside model learning.",
                ),
            ],
            reward_trends=self._build_metric_series(
                "reward", "Reward", ["#38bdf8", "#8b5cf6", "#14b8a6"], limit=180
            ),
            loss_trends=self._build_metric_series(
                "loss", "Loss", ["#fb7185", "#f59e0b", "#e879f9"], limit=180
            ),
            throughput_trends=self._build_metric_series(
                "throughput", "Tokens/sec", ["#22c55e", "#2dd4bf", "#60a5fa"], limit=180
            ),
            best_runs=best_runs,
            failure_causes=causes,
            alerts=alerts,
        )

    def inspector(self, *, limit: int = 12) -> InspectorResponse:
        rows = self._storage.recent_prompts_with_outputs(limit=limit)
        rewards_by_step = {
            (reward.run_id, reward.step): reward
            for reward in self._storage.recent_rewards(limit=80)
        }
        examples: list[TrainingInspectorRow] = []
        for row in rows:
            prompt = PromptRecord(
                prompt_id=row["prompt_id"],
                run_id=row["run_id"],
                step=row["step"],
                timestamp=row["timestamp"],
                scenario=row["scenario"],
                input_text=row["input_text"],
                metadata=row["prompt_metadata"],
            )
            output = OutputRecord(
                output_id=row["output_id"] or f"missing-{row['prompt_id']}",
                run_id=row["run_id"],
                prompt_id=row["prompt_id"],
                step=row["step"],
                timestamp=row["timestamp"],
                output_text=row["output_text"] or "No output captured yet.",
                label=row["label"] or "pending",
                score=float(row["score"] or 0.0),
                metadata=row["output_metadata"],
            )
            examples.append(
                TrainingInspectorRow(
                    prompt=prompt,
                    output=output,
                    reward=rewards_by_step.get((row["run_id"], row["step"])),
                )
            )
        return InspectorResponse(
            stats=[
                MetricCard(
                    id="inspected-prompts",
                    label="Prompt / Output Pairs",
                    value=str(len(examples)),
                    delta=f"{self._storage.count('prompts')} total",
                    direction="up",
                    hint="Recent captured batches and generations.",
                ),
                MetricCard(
                    id="bad-generations",
                    label="Bad Generations",
                    value=str(
                        sum(
                            1
                            for example in examples
                            if example.output.label == "bad_generation"
                        )
                    ),
                    delta="Anomaly-aware",
                    direction="down",
                    hint="Useful for mode collapse and quality regressions.",
                ),
                MetricCard(
                    id="avg-reward",
                    label="Average Assigned Reward",
                    value=f"{(sum((example.reward.reward_total if example.reward else 0.0) for example in examples) / max(1, len(examples))):.2f}",
                    delta="Streaming",
                    direction="steady",
                    hint="Reward labels tied to specific prompt/output pairs.",
                ),
            ],
            examples=examples,
            prompt_series=self._build_metric_series(
                "reward", "Reward", ["#38bdf8", "#8b5cf6", "#14b8a6"], limit=80
            ),
        )

    def alerts_center(self, *, limit: int = 24) -> AlertsResponse:
        alerts = self._storage.recent_alerts(limit=limit)
        events = [
            event
            for event in self._storage.recent_events(limit=limit * 2)
            if event.severity in {"high", "critical"}
        ]
        return AlertsResponse(
            stats=[
                MetricCard(
                    id="alerts-open",
                    label="Open Alerts",
                    value=str(self._storage.count_open_alerts()),
                    delta=f"{len(alerts)} recent",
                    direction="down",
                    hint="Realtime health checks are watching reward, loss, stagnation, and repair regressions.",
                ),
                MetricCard(
                    id="critical-events",
                    label="Critical Events",
                    value=str(
                        sum(1 for event in events if event.severity == "critical")
                    ),
                    delta="Auto-detected",
                    direction="down",
                    hint="Pipeline anomalies surfaced without manual inspection.",
                ),
                MetricCard(
                    id="repair-regressions",
                    label="Repair Regressions",
                    value=str(
                        sum(
                            1
                            for alert in alerts
                            if alert.alert_type == "repair_regression"
                        )
                    ),
                    delta="Linked to ReMorph engine",
                    direction="down",
                    hint="Keeps model training quality tied to downstream API outcomes.",
                ),
            ],
            alerts=alerts,
            events=events,
        )

    def remorph_engine(self, *, limit: int = 12) -> RemorphEngineResponse:
        repairs = self._storage.recent_repairs(limit=limit)
        runtime_summary = self._artifact_repo.runtime_summary()
        openenv_training = self._artifact_repo.submission_training_summary()
        return RemorphEngineResponse(
            stats=[
                MetricCard(
                    id="repair-success",
                    label="Repair Success Rate",
                    value=f"{self._repair_success_rate(repairs) * 100:.1f}%",
                    delta=f"{len(repairs)} recent events",
                    direction="up",
                    hint="Simulated repair outcomes persisted in the observability platform.",
                ),
                MetricCard(
                    id="runtime-healings",
                    label="Runtime Healings",
                    value=str(runtime_summary.get("total_healings", 0)),
                    delta=f"{runtime_summary.get('average_processing_ms', 0)}ms avg",
                    direction="steady",
                    hint="Pulled from sibling ReMorph runtime telemetry.",
                ),
                MetricCard(
                    id="training-examples",
                    label="Training Examples",
                    value=str(openenv_training.get("training_example_count", 0)),
                    delta=f"{openenv_training.get('eval_scenario_count', 0)} eval scenarios",
                    direction="up",
                    hint="Grounds the observability story in real ReMorph training artifacts.",
                ),
            ],
            repairs=repairs,
            recent_events=[
                event
                for event in self._storage.recent_events(limit=limit * 2)
                if event.event_type.startswith("repair")
            ][:limit],
        )

    def system_health(self) -> SystemHealthResponse:
        runs = self._current_runs(limit=24)
        return SystemHealthResponse(
            generated_at=iso_now(),
            ingest_rate_per_sec=self._rate(self._ingest_timestamps),
            stream_rate_per_sec=self._rate(self._publish_timestamps),
            storage_latency_ms=round(
                sum(self._storage_latency_ms) / max(1, len(self._storage_latency_ms)), 2
            ),
            active_run_count=len(
                [
                    run
                    for run in runs
                    if run.status in {"running", "degraded", "completed"}
                ]
            ),
            queue_depth=self._hub.queue_depth(),
            alerts_open=self._storage.count_open_alerts(),
        )

    def ingest_metrics(self, payload: IngestMetricsRequest) -> dict[str, int]:
        for item in payload.items:
            self._store_metric(item)
        return {"stored": len(payload.items)}

    def ingest_events(self, payload: IngestEventsRequest) -> dict[str, int]:
        for item in payload.items:
            self._store_event(item)
        return {"stored": len(payload.items)}

    def ingest_prompts(self, payload: IngestPromptsRequest) -> dict[str, int]:
        for item in payload.items:
            self._store_prompt(item)
        return {"stored": len(payload.items)}

    def ingest_outputs(self, payload: IngestOutputsRequest) -> dict[str, int]:
        for item in payload.items:
            self._store_output(item)
        return {"stored": len(payload.items)}

    def ingest_rewards(self, payload: IngestRewardsRequest) -> dict[str, int]:
        for item in payload.items:
            self._store_reward(item)
        return {"stored": len(payload.items)}

    def ingest_repairs(self, payload: IngestRepairsRequest) -> dict[str, int]:
        for item in payload.items:
            self._store_repair(item)
        return {"stored": len(payload.items)}

    def _bootstrap_from_openenv_artifacts(self) -> None:
        rollouts = self._artifact_repo.submission_rollouts(limit=600)
        training_summary = self._artifact_repo.submission_training_summary()
        reward_history = self._artifact_repo.submission_reward_history()
        loss_history = self._artifact_repo.submission_loss_history()
        if not rollouts:
            return

        now = utc_now()
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rollouts:
            scenario = str(row.get("scenario_id") or "openenv-scenario")
            grouped[scenario].append(row)
        for rows in grouped.values():
            rows.sort(key=lambda item: int(item.get("step_index", 0)))

        selected = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[
            :6
        ]
        for index, (scenario_id, rows) in enumerate(selected):
            run_id = f"openenv-{scenario_id}"
            total_steps = max(1, len(rows))
            completed_steps = int(rows[-1].get("step_index", total_steps - 1)) + 1
            latest_reward = float(rows[-1].get("raw_reward", 0.0))
            latest_confidence = float(rows[-1].get("confidence", 0.0))
            success_rate = sum(1 for row in rows if bool(row.get("success"))) / max(
                1, len(rows)
            )
            avg_raw_reward = sum(
                float(row.get("raw_reward", 0.0)) for row in rows
            ) / max(1, len(rows))
            started = (
                (now - timedelta(minutes=45 - index * 6))
                .replace(microsecond=0)
                .isoformat()
            )
            updated = (
                (now - timedelta(seconds=index * 4)).replace(microsecond=0).isoformat()
            )
            run = RunRecord(
                run_id=run_id,
                name=scenario_id.replace("-", " "),
                model_name=str(
                    training_summary.get("trainer", "supervised_structured_policy")
                ),
                trainer="OpenEnv submission",
                source="artifact replay",
                status="completed" if rows[-1].get("done") else "degraded",
                started_at=started,
                updated_at=updated,
                current_step=completed_steps,
                total_steps=total_steps,
                progress=min(1.0, completed_steps / max(1, total_steps)),
                throughput_tokens_per_sec=max(320.0, 760.0 - index * 35),
                gpu_utilization=max(28.0, 74.0 - index * 6),
                reward_latest=latest_reward,
                loss_latest=max(0.06, 1.8 - max(0.0, avg_raw_reward / 16.0)),
                success_rate=success_rate,
                anomaly_score=max(0.02, 1.0 - latest_confidence),
                last_alert=(
                    None if rows[-1].get("success") else "openenv replay mismatch"
                ),
                tags=[
                    "openenv",
                    "artifact",
                    str(rows[-1].get("policy_name", "policy")),
                ],
            )
            self._timed_store(
                lambda run_record=run: self._storage.upsert_run(run_record)
            )
            self._record_ingest()

            for offset, row in enumerate(rows):
                ts = (
                    (now - timedelta(seconds=(len(rows) - offset) * 3 + index * 4))
                    .replace(microsecond=0)
                    .isoformat()
                )
                raw_reward = float(row.get("raw_reward", 0.0))
                confidence = float(row.get("confidence", 0.0))
                metric_seed = f"{scenario_id}:{offset}"
                metrics = [
                    MetricSample(
                        metric_id=str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:reward")
                        ),
                        run_id=run_id,
                        metric_name="reward",
                        split="eval",
                        step=offset + 1,
                        timestamp=ts,
                        value=raw_reward,
                    ),
                    MetricSample(
                        metric_id=str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:loss")
                        ),
                        run_id=run_id,
                        metric_name="loss",
                        split="eval",
                        step=offset + 1,
                        timestamp=ts,
                        value=max(0.08, 1.8 - (raw_reward / 22.0)),
                    ),
                    MetricSample(
                        metric_id=str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:throughput")
                        ),
                        run_id=run_id,
                        metric_name="throughput",
                        split="eval",
                        step=offset + 1,
                        timestamp=ts,
                        value=max(280.0, 880.0 - (1 - confidence) * 210.0),
                    ),
                    MetricSample(
                        metric_id=str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:gpu")
                        ),
                        run_id=run_id,
                        metric_name="gpu_utilization",
                        split="eval",
                        step=offset + 1,
                        timestamp=ts,
                        value=max(20.0, min(98.0, 58.0 + confidence * 33.0)),
                    ),
                ]
                for metric in metrics:
                    self._store_metric(metric)

                observation = self._parse_observation(row.get("observation_signature"))
                action = (
                    row.get("action", {}) if isinstance(row.get("action"), dict) else {}
                )
                event = EventRecord(
                    event_id=str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:event")
                    ),
                    run_id=run_id,
                    event_type=f"openenv.{row.get('belief', 'step')}",
                    severity=self._severity_from_reward(
                        raw_reward, bool(row.get("success"))
                    ),
                    timestamp=ts,
                    message=self._event_message_for_rollout(row),
                    payload={
                        "scenario_id": scenario_id,
                        "workflow_id": row.get("workflow_id"),
                        "policy_name": row.get("policy_name"),
                        "step_index": row.get("step_index"),
                        "done": bool(row.get("done")),
                        "success": bool(row.get("success")),
                    },
                )
                self._store_event(event)

                prompt = PromptRecord(
                    prompt_id=str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:prompt")
                    ),
                    run_id=run_id,
                    step=offset + 1,
                    timestamp=ts,
                    scenario=scenario_id,
                    input_text=str(
                        observation.get("error_signal", {}).get("message")
                        or "Analyze failed API request and propose safe repair."
                    ),
                    metadata={"observation": observation},
                )
                self._store_prompt(prompt)

                output = OutputRecord(
                    output_id=str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:output")
                    ),
                    run_id=run_id,
                    prompt_id=prompt.prompt_id,
                    step=offset + 1,
                    timestamp=ts,
                    output_text=json.dumps(action),
                    label=(
                        "good_generation"
                        if bool(row.get("success"))
                        else "bad_generation"
                    ),
                    score=confidence,
                    metadata={
                        "belief": row.get("belief"),
                        "telemetry_group": row.get("telemetry_group"),
                    },
                )
                self._store_output(output)

                reward_record = RewardRecord(
                    reward_id=str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:reward_record")
                    ),
                    run_id=run_id,
                    step=offset + 1,
                    timestamp=ts,
                    reward_total=raw_reward,
                    components={
                        key: float(value)
                        for key, value in (row.get("reward_breakdown") or {}).items()
                        if isinstance(value, (int, float))
                    },
                )
                self._store_reward(reward_record)

                if bool(row.get("done")) and not bool(row.get("success")):
                    alert = AlertRecord(
                        alert_id=str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:alert")
                        ),
                        run_id=run_id,
                        alert_type="repair_regression",
                        severity="high",
                        timestamp=ts,
                        title="OpenEnv scenario failed",
                        detail=f"{scenario_id} failed after {int(row.get('step_index', 0)) + 1} steps.",
                        resolved=False,
                        confidence=max(0.55, confidence),
                    )
                    self._store_alert(alert)

                if action.get("action_type") in {
                    "repair_route",
                    "repair_payload",
                    "repair_auth",
                }:
                    failed_request = (
                        observation.get("failed_request", {})
                        if isinstance(observation, dict)
                        else {}
                    )
                    healed_request = {
                        "method": action.get("target_method"),
                        "path": action.get("target_path"),
                        "headers": action.get("header_patch"),
                        "query": action.get("query_patch"),
                        "body": action.get("body_patch"),
                    }
                    repair = RepairRecord(
                        repair_id=str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"{metric_seed}:repair")
                        ),
                        run_id=run_id,
                        scenario_id=scenario_id,
                        timestamp=ts,
                        failed_request=(
                            failed_request if isinstance(failed_request, dict) else {}
                        ),
                        repair_reasoning=str(
                            action.get("reason")
                            or "Derived from OpenEnv artifact replay."
                        ),
                        healed_request=healed_request,
                        retry_result=(
                            "200 OK" if bool(row.get("success")) else "needs_review"
                        ),
                        confidence=confidence,
                        outcome="success" if bool(row.get("success")) else "failed",
                        safe_abstained=False,
                    )
                    self._store_repair(repair)

        self._append_openenv_history_metrics(
            reward_history=reward_history, loss_history=loss_history, now=now
        )

    def _append_openenv_history_metrics(
        self, *, reward_history: list[dict], loss_history: list[dict], now: datetime
    ) -> None:
        for index, row in enumerate(reward_history[:40]):
            epoch = int(row.get("epoch", index))
            split = str(row.get("split", "eval"))
            run_id = f"openenv-summary-{split}"
            ts = (
                (now - timedelta(minutes=40 - index)).replace(microsecond=0).isoformat()
            )
            value = float(row.get("average_raw_reward", 0.0))
            self._store_metric(
                MetricSample(
                    metric_id=str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"openenv-history-reward:{split}:{epoch}",
                        )
                    ),
                    run_id=run_id,
                    metric_name="reward",
                    split=split,
                    step=epoch + 1,
                    timestamp=ts,
                    value=value,
                )
            )
        for index, row in enumerate(loss_history[:40]):
            epoch = int(row.get("epoch", index))
            split = str(row.get("split", "train"))
            run_id = f"openenv-summary-{split}"
            ts = (
                (now - timedelta(minutes=35 - index)).replace(microsecond=0).isoformat()
            )
            mismatch_rate = float(row.get("mismatch_rate", 0.0))
            self._store_metric(
                MetricSample(
                    metric_id=str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL, f"openenv-history-loss:{split}:{epoch}"
                        )
                    ),
                    run_id=run_id,
                    metric_name="loss",
                    split=split,
                    step=epoch + 1,
                    timestamp=ts,
                    value=max(0.06, mismatch_rate * 2.5),
                )
            )

    def _artifact_stream_loop(self) -> None:
        while not self._stop_event.is_set():
            snapshot = EventPayload(
                channel="metrics",
                event_type="command_center.snapshot",
                timestamp=iso_now(),
                data=self.command_center().model_dump(mode="json"),
            )
            self._publish("metrics", snapshot)

            recent_events = self._storage.recent_events(limit=24)
            if recent_events:
                event = recent_events[self._artifact_cursor % len(recent_events)]
                self._publish(
                    "logs",
                    EventPayload(
                        channel="logs",
                        event_type=event.event_type,
                        timestamp=event.timestamp,
                        data=event.model_dump(mode="json"),
                    ),
                )

            recent_alerts = self._storage.recent_alerts(limit=12)
            if recent_alerts and self._artifact_cursor % 3 == 0:
                alert = recent_alerts[self._artifact_cursor % len(recent_alerts)]
                self._publish(
                    "alerts",
                    EventPayload(
                        channel="alerts",
                        event_type=alert.alert_type,
                        timestamp=alert.timestamp,
                        data=alert.model_dump(mode="json"),
                    ),
                )

            recent_repairs = self._storage.recent_repairs(limit=16)
            if recent_repairs and self._artifact_cursor % 2 == 0:
                repair = recent_repairs[self._artifact_cursor % len(recent_repairs)]
                self._publish(
                    "repairs",
                    EventPayload(
                        channel="repairs",
                        event_type="repair.update",
                        timestamp=repair.timestamp,
                        data=repair.model_dump(mode="json"),
                    ),
                )

            self._artifact_cursor += 1
            time.sleep(0.8)

    def _parse_observation(self, raw_observation: object) -> dict:
        if isinstance(raw_observation, dict):
            return raw_observation
        if isinstance(raw_observation, str):
            try:
                payload = json.loads(raw_observation)
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def _severity_from_reward(self, raw_reward: float, success: bool) -> str:
        if success:
            return "info"
        if raw_reward <= -10:
            return "critical"
        if raw_reward <= -3:
            return "high"
        return "medium"

    def _event_message_for_rollout(self, row: dict) -> str:
        scenario = row.get("scenario_id", "scenario")
        belief = row.get("belief", "policy")
        reward = float(row.get("raw_reward", 0.0))
        return f"{scenario}: {belief} raw_reward={reward:.2f} success={bool(row.get('success'))}"

    def _seed_runs(self) -> None:
        with self._state_lock:
            if self._runs:
                return
            for slot in range(4):
                run = self._new_run(slot)
                self._runs[run.run_id] = run
                self._storage.upsert_run(self._to_run_record(run))

    def _new_run(self, slot: int) -> SimRun:
        started_at = iso_now()
        model_names = ["Qwen2.5-0.5B", "Llama-3.2-1B", "Phi-3-mini", "Mistral-7B"]
        trainers = ["TRL GRPO", "HF Trainer", "Unsloth", "Supervised Policy"]
        sources = ["Colab", "Local GPU", "Cloud A10G", "HF Space Replay"]
        names = ["reward-scan", "route-healing", "payload-policy", "repair-eval"]
        return SimRun(
            run_id=f"run-{slot}-{uuid.uuid4().hex[:8]}",
            slot=slot,
            name=f"{names[slot]}-{self._rng.randint(100, 999)}",
            model_name=model_names[slot % len(model_names)],
            trainer=trainers[slot % len(trainers)],
            source=sources[slot % len(sources)],
            started_at=started_at,
            total_steps=self._rng.randint(280, 520),
            tags=(
                ["remorph", "api-healing", "reward-model"]
                if slot % 2 == 0
                else ["observability", "realtime"]
            ),
        )

    def _simulate_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._state_lock:
                active_runs = list(self._runs.values())
                if not active_runs:
                    self._seed_runs()
                    active_runs = list(self._runs.values())
                run = active_runs[self._round_robin % len(active_runs)]
                self._round_robin += 1
            self._tick_run(run)
            time.sleep(0.02)

    def _tick_run(self, run: SimRun) -> None:
        if run.current_step >= run.total_steps:
            completion_event = self._build_event(
                run,
                "run.completed",
                "info",
                f"{run.name} reached the final checkpoint.",
            )
            self._store_event(completion_event)
            with self._state_lock:
                self._runs.pop(run.run_id, None)
                replacement = self._new_run(run.slot)
                self._runs[replacement.run_id] = replacement
                self._storage.upsert_run(self._to_run_record(replacement))
            return

        run.current_step += 1
        progress = run.current_step / run.total_steps
        anomaly_penalty = 0.0
        loss_penalty = 0.0
        alert: AlertRecord | None = None

        if self._rng.random() < 0.018:
            anomaly_penalty = self._rng.uniform(0.12, 0.28)
            alert = self._build_alert(
                run, "reward_drop", "high", "Reward collapse detected on live stream."
            )
        elif self._rng.random() < 0.018:
            loss_penalty = self._rng.uniform(0.4, 0.9)
            alert = self._build_alert(
                run, "loss_spike", "critical", "Loss spike exceeded expected band."
            )
        elif self._rng.random() < 0.012:
            alert = self._build_alert(
                run,
                "stalled_run",
                "medium",
                "Step progression slowed below expected throughput.",
            )
        elif self._rng.random() < 0.010:
            alert = self._build_alert(
                run,
                "bad_generation",
                "medium",
                "Generated output drifted from expected repair pattern.",
            )

        run.reward_latest = max(
            0.05,
            0.25
            + progress * 0.9
            + math.sin(run.current_step / 11 + run.slot) * 0.06
            - anomaly_penalty,
        )
        run.loss_latest = max(
            0.05,
            1.9
            - progress * 1.45
            + abs(math.sin(run.current_step / 9 + run.slot)) * 0.08
            + loss_penalty,
        )
        run.success_rate = max(
            0.12, min(0.99, 0.42 + progress * 0.48 - anomaly_penalty * 0.35)
        )
        run.throughput = max(
            420.0,
            950
            + math.sin(run.current_step / 8 + run.slot) * 160
            + self._rng.uniform(-70, 60),
        )
        run.gpu_util = max(
            28.0,
            min(
                99.0,
                72
                + math.cos(run.current_step / 10 + run.slot) * 14
                + self._rng.uniform(-5, 5),
            ),
        )
        run.anomaly_score = min(
            1.0, 0.12 + abs(anomaly_penalty) * 2.6 + abs(loss_penalty) * 0.5
        )
        run.status = "degraded" if alert else "running"
        run.last_alert = alert.title if alert else None

        run_record = self._to_run_record(run)
        self._timed_store(lambda: self._storage.upsert_run(run_record))

        timestamp = iso_now()
        metrics = [
            MetricSample(
                metric_id=str(uuid.uuid4()),
                run_id=run.run_id,
                metric_name="reward",
                split="train",
                step=run.current_step,
                timestamp=timestamp,
                value=run.reward_latest,
            ),
            MetricSample(
                metric_id=str(uuid.uuid4()),
                run_id=run.run_id,
                metric_name="loss",
                split="train",
                step=run.current_step,
                timestamp=timestamp,
                value=run.loss_latest,
            ),
            MetricSample(
                metric_id=str(uuid.uuid4()),
                run_id=run.run_id,
                metric_name="throughput",
                split="train",
                step=run.current_step,
                timestamp=timestamp,
                value=run.throughput,
            ),
            MetricSample(
                metric_id=str(uuid.uuid4()),
                run_id=run.run_id,
                metric_name="gpu_utilization",
                split="train",
                step=run.current_step,
                timestamp=timestamp,
                value=run.gpu_util,
            ),
        ]
        for metric in metrics:
            self._store_metric(metric)

        log_event = self._build_event(
            run,
            "training.step",
            "info",
            f"step={run.current_step} reward={run.reward_latest:.3f} loss={run.loss_latest:.3f} throughput={run.throughput:.0f}",
            {"progress": round(run.current_step / run.total_steps, 4)},
        )
        self._store_event(log_event)

        reward = RewardRecord(
            reward_id=str(uuid.uuid4()),
            run_id=run.run_id,
            step=run.current_step,
            timestamp=timestamp,
            reward_total=run.reward_latest,
            components={
                "repair_success": round(run.reward_latest * 0.55, 4),
                "efficiency": round(run.reward_latest * 0.2, 4),
                "safety": round(run.reward_latest * 0.25, 4),
            },
        )
        self._store_reward(reward)

        if run.current_step % 6 == 0:
            prompt = self._build_prompt(run)
            output = self._build_output(
                run, prompt.prompt_id, alert_type=alert.alert_type if alert else None
            )
            self._store_prompt(prompt)
            self._store_output(output)

        if run.current_step % 10 == 0:
            repair = self._build_repair(
                run, alert_type=alert.alert_type if alert else None
            )
            self._store_repair(repair)

        if alert:
            self._store_alert(alert)

        snapshot_payload = EventPayload(
            channel="metrics",
            event_type="command_center.snapshot",
            timestamp=iso_now(),
            data=self.command_center().model_dump(mode="json"),
        )
        self._publish("metrics", snapshot_payload)
        self._publish(
            "runs",
            EventPayload(
                channel="runs",
                event_type="run.update",
                timestamp=iso_now(),
                data=run_record.model_dump(mode="json"),
            ),
        )

    def _store_metric(self, metric: MetricSample) -> None:
        self._timed_store(lambda: self._storage.insert_metric(metric))
        self._record_ingest()

    def _store_event(self, event: EventRecord) -> None:
        self._timed_store(lambda: self._storage.insert_event(event))
        self._record_ingest()
        self._publish(
            "logs",
            EventPayload(
                channel="logs",
                event_type=event.event_type,
                timestamp=event.timestamp,
                data=event.model_dump(mode="json"),
            ),
        )

    def _store_prompt(self, prompt: PromptRecord) -> None:
        self._timed_store(lambda: self._storage.insert_prompt(prompt))
        self._record_ingest()

    def _store_output(self, output: OutputRecord) -> None:
        self._timed_store(lambda: self._storage.insert_output(output))
        self._record_ingest()

    def _store_reward(self, reward: RewardRecord) -> None:
        self._timed_store(lambda: self._storage.insert_reward(reward))
        self._record_ingest()

    def _store_alert(self, alert: AlertRecord) -> None:
        self._timed_store(lambda: self._storage.insert_alert(alert))
        self._record_ingest()
        self._publish(
            "alerts",
            EventPayload(
                channel="alerts",
                event_type=alert.alert_type,
                timestamp=alert.timestamp,
                data=alert.model_dump(mode="json"),
            ),
        )

    def _store_repair(self, repair: RepairRecord) -> None:
        self._timed_store(lambda: self._storage.insert_repair(repair))
        self._record_ingest()
        self._publish(
            "repairs",
            EventPayload(
                channel="repairs",
                event_type="repair.update",
                timestamp=repair.timestamp,
                data=repair.model_dump(mode="json"),
            ),
        )

    def _publish(self, channel: str, payload: EventPayload) -> None:
        delivered = self._hub.publish(channel, payload)
        if delivered or channel in {"metrics", "logs", "alerts", "repairs", "runs"}:
            self._publish_timestamps.append(time.time())

    def _record_ingest(self) -> None:
        self._ingest_timestamps.append(time.time())

    def _timed_store(self, fn) -> None:
        started = time.perf_counter()
        fn()
        self._storage_latency_ms.append((time.perf_counter() - started) * 1000)

    def _build_event(
        self,
        run: SimRun,
        event_type: str,
        severity: str,
        message: str,
        payload: dict | None = None,
    ) -> EventRecord:
        return EventRecord(
            event_id=str(uuid.uuid4()),
            run_id=run.run_id,
            event_type=event_type,
            severity=severity,
            timestamp=iso_now(),
            message=message,
            payload=payload or {},
        )

    def _build_prompt(self, run: SimRun) -> PromptRecord:
        scenarios = [
            "auth_drift_missing_token",
            "route_drift_v2_transition",
            "payload_drift_nested_shape",
            "reward_collapse_recovery",
        ]
        scenario = scenarios[(run.current_step + run.slot) % len(scenarios)]
        return PromptRecord(
            prompt_id=str(uuid.uuid4()),
            run_id=run.run_id,
            step=run.current_step,
            timestamp=iso_now(),
            scenario=scenario,
            input_text=(
                f"Observe failed request context at step {run.current_step}. "
                f"Predict the best structured repair action for {scenario}."
            ),
            metadata={"batch_size": 4 + run.slot, "temperature": 0.2 + run.slot * 0.05},
        )

    def _build_output(
        self, run: SimRun, prompt_id: str, *, alert_type: str | None
    ) -> OutputRecord:
        is_bad = (
            alert_type in {"bad_generation", "mode_collapse"}
            or self._rng.random() < 0.08
        )
        return OutputRecord(
            output_id=str(uuid.uuid4()),
            run_id=run.run_id,
            prompt_id=prompt_id,
            step=run.current_step,
            timestamp=iso_now(),
            output_text=(
                '{"action_type":"repair_route","target_path":"/api/v2/users","reason":"Move to the active route."}'
                if not is_bad
                else '{"action_type":"repair_auth","target_path":null,"reason":"Low confidence malformed output."}'
            ),
            label="bad_generation" if is_bad else "good_generation",
            score=max(0.08, min(0.98, run.success_rate - (0.25 if is_bad else -0.04))),
            metadata={"alert_type": alert_type},
        )

    def _build_alert(
        self, run: SimRun, alert_type: str, severity: str, detail: str
    ) -> AlertRecord:
        return AlertRecord(
            alert_id=str(uuid.uuid4()),
            run_id=run.run_id,
            alert_type=alert_type,
            severity=severity,
            timestamp=iso_now(),
            title=alert_type.replace("_", " ").title(),
            detail=detail,
            resolved=False,
            confidence=round(self._rng.uniform(0.72, 0.97), 2),
        )

    def _build_repair(self, run: SimRun, *, alert_type: str | None) -> RepairRecord:
        outcomes = ["success", "success", "success", "failed", "abstained"]
        outcome = (
            "failed"
            if alert_type == "repair_regression"
            else outcomes[self._rng.randint(0, len(outcomes) - 1)]
        )
        failed_request = {
            "method": "POST",
            "path": "/api/v1/orders",
            "headers": {"Authorization": "Bearer demo-token"},
            "body": {"order_id": f"O-{run.current_step}", "amount": "1900"},
        }
        healed_request = None
        if outcome != "abstained":
            healed_request = {
                "method": "POST",
                "path": "/api/v2/orders",
                "headers": {
                    "Authorization": "Bearer demo-token",
                    "x-tenant-id": "north",
                },
                "body": {"order_id": f"O-{run.current_step}", "amount": 1900},
            }
        return RepairRecord(
            repair_id=str(uuid.uuid4()),
            run_id=run.run_id,
            scenario_id=f"repair-scenario-{run.current_step % 5}",
            timestamp=iso_now(),
            failed_request=failed_request,
            repair_reasoning="Detect route drift, coerce payload type, and retry with contract-backed tenant headers.",
            healed_request=healed_request,
            retry_result=(
                "200 OK"
                if outcome == "success"
                else "safe_abstain" if outcome == "abstained" else "422 persists"
            ),
            confidence=round(self._rng.uniform(0.71, 0.96), 2),
            outcome=outcome,
            safe_abstained=outcome == "abstained",
        )

    def _to_run_record(self, run: SimRun) -> RunRecord:
        updated_at = iso_now()
        return RunRecord(
            run_id=run.run_id,
            name=run.name,
            model_name=run.model_name,
            trainer=run.trainer,
            source=run.source,
            status=run.status,  # type: ignore[arg-type]
            started_at=run.started_at,
            updated_at=updated_at,
            current_step=run.current_step,
            total_steps=run.total_steps,
            progress=round(run.current_step / max(1, run.total_steps), 4),
            throughput_tokens_per_sec=round(run.throughput, 2),
            gpu_utilization=round(run.gpu_util, 2),
            reward_latest=round(run.reward_latest, 4),
            loss_latest=round(run.loss_latest, 4),
            success_rate=round(run.success_rate, 4),
            anomaly_score=round(run.anomaly_score, 4),
            last_alert=run.last_alert,
            tags=run.tags or [],
        )

    def _overview_cards(self, runs: list[RunRecord]) -> list[MetricCard]:
        counts = self._storage.table_counts()
        avg_reward = sum(run.reward_latest for run in runs) / max(1, len(runs))
        avg_loss = sum(run.loss_latest for run in runs) / max(1, len(runs))
        return [
            MetricCard(
                id="active-runs",
                label="Active Runs",
                value=str(
                    len([run for run in runs if run.status in {"running", "degraded"}])
                ),
                delta=f"{counts['runs']} persisted",
                direction="up",
                hint="Multiple concurrent simulated jobs feeding storage and realtime APIs.",
            ),
            MetricCard(
                id="reward-live",
                label="Live Reward",
                value=f"{avg_reward:.2f}",
                delta=f"{self._rate(self._ingest_timestamps):.1f} ing/s",
                direction="up",
                hint="Average latest reward across active runs.",
            ),
            MetricCard(
                id="loss-live",
                label="Live Loss",
                value=f"{avg_loss:.2f}",
                delta=f"{self._rate(self._publish_timestamps):.1f} stream/s",
                direction="down",
                hint="Average latest loss across active runs.",
            ),
            MetricCard(
                id="throughput",
                label="Token Throughput",
                value=f"{sum(run.throughput_tokens_per_sec for run in runs):,.0f}",
                delta="tokens/s aggregate",
                direction="up",
                hint="Total throughput across the active fleet.",
            ),
            MetricCard(
                id="open-alerts",
                label="Open Alerts",
                value=str(self._storage.count_open_alerts()),
                delta=f"{counts['alerts']} total",
                direction="down",
                hint="Realtime anomaly engine watches loss, reward, stagnation, and generation quality.",
            ),
            MetricCard(
                id="repairs",
                label="ReMorph Repair Events",
                value=str(counts["repairs"]),
                delta=f"{counts['events']} total events",
                direction="steady",
                hint="Model observability stays linked to API healing outcomes.",
            ),
        ]

    def _build_metric_series(
        self, metric_name: str, label: str, colors: list[str], *, limit: int = 120
    ) -> list[Series]:
        runs = self._current_runs(limit=3)
        series: list[Series] = []
        for index, run in enumerate(runs):
            samples = self._storage.recent_metrics(
                [metric_name], limit_per_metric=limit, run_id=run.run_id
            )
            points = [
                TimePoint(
                    timestamp=sample.timestamp,
                    value=sample.value,
                    run_id=run.run_id,
                    label=run.name,
                )
                for sample in samples
            ]
            series.append(
                Series(
                    id=f"{metric_name}-{run.run_id}",
                    label=f"{run.name} {label}",
                    color=colors[index % len(colors)],
                    points=points,
                )
            )
        return series

    def _current_runs(self, *, limit: int) -> list[RunRecord]:
        runs = self._storage.list_runs(limit=120)
        if self._data_source_mode in {"openenv", "artifacts", "artifact"}:
            filtered = [run for run in runs if run.source == "artifact replay"]
            if filtered:
                return filtered[:limit]
        return runs[:limit]

    def _failure_causes(self, alerts: list[AlertRecord]) -> list[FailureCauseRow]:
        counts: dict[str, int] = defaultdict(int)
        severity_rank: dict[str, str] = {}
        for alert in alerts:
            counts[alert.alert_type] += 1
            severity_rank[alert.alert_type] = alert.severity
        ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        return [
            FailureCauseRow(
                name=name.replace("_", " ").title(),
                count=count,
                severity=severity_rank[name],
            )
            for name, count in ordered
        ]

    def _repair_success_rate(self, repairs: list[RepairRecord]) -> float:
        if not repairs:
            return 0.0
        return sum(1 for repair in repairs if repair.outcome == "success") / len(
            repairs
        )

    def _paginate(self, items: list, *, page: int, page_size: int) -> PageResponse:
        safe_page = max(1, page)
        safe_size = max(1, page_size)
        start = (safe_page - 1) * safe_size
        end = start + safe_size
        return PageResponse(
            items=items[start:end],
            total=len(items),
            page=safe_page,
            page_size=safe_size,
        )

    def _rate(self, timestamps: deque[float]) -> float:
        if len(timestamps) < 2:
            return 0.0
        cutoff = time.time() - 1.0
        recent = [timestamp for timestamp in timestamps if timestamp >= cutoff]
        return round(float(len(recent)), 2)
