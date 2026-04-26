from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from typing import Any

from app.models import (
    AlertRecord,
    EventRecord,
    MetricSample,
    OutputRecord,
    PromptRecord,
    RepairRecord,
    RewardRecord,
    RunRecord,
)
from app.repositories.base import event_log_path, runtime_root

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - exercised only when postgres backend is requested without dependency
    psycopg = None
    dict_row = None
    _PSYCOPG_IMPORT_ERROR = exc
else:
    _PSYCOPG_IMPORT_ERROR = None


class PostgresObservabilityStorage:
    def __init__(self, dsn: str) -> None:
        if psycopg is None or dict_row is None:
            raise RuntimeError("Postgres backend requested but psycopg is not installed.") from _PSYCOPG_IMPORT_ERROR
        if not dsn:
            raise ValueError("Postgres DSN is required when STORAGE_BACKEND=postgres.")
        runtime_root()
        self._log_path = event_log_path()
        self._lock = threading.Lock()
        self._conn = psycopg.connect(dsn, autocommit=False, row_factory=dict_row)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    trainer TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_step INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    progress DOUBLE PRECISION NOT NULL,
                    throughput_tokens_per_sec DOUBLE PRECISION NOT NULL,
                    gpu_utilization DOUBLE PRECISION NOT NULL,
                    reward_latest DOUBLE PRECISION NOT NULL,
                    loss_latest DOUBLE PRECISION NOT NULL,
                    success_rate DOUBLE PRECISION NOT NULL,
                    anomaly_score DOUBLE PRECISION NOT NULL,
                    last_alert TEXT,
                    tags_json TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    metric_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    split TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    value DOUBLE PRECISION NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS prompts (
                    prompt_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS outputs (
                    output_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    prompt_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    output_text TEXT NOT NULL,
                    label TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rewards (
                    reward_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    reward_total DOUBLE PRECISION NOT NULL,
                    components_json TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    resolved INTEGER NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS repairs (
                    repair_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    failed_request_json TEXT NOT NULL,
                    repair_reasoning TEXT NOT NULL,
                    healed_request_json TEXT,
                    retry_result TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    outcome TEXT NOT NULL,
                    safe_abstained INTEGER NOT NULL
                );
                """
            )
            self._conn.commit()

    def upsert_run(self, run: RunRecord) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (
                    run_id, name, model_name, trainer, source, status, started_at, updated_at,
                    current_step, total_steps, progress, throughput_tokens_per_sec, gpu_utilization,
                    reward_latest, loss_latest, success_rate, anomaly_score, last_alert, tags_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(run_id) DO UPDATE SET
                    name=EXCLUDED.name,
                    model_name=EXCLUDED.model_name,
                    trainer=EXCLUDED.trainer,
                    source=EXCLUDED.source,
                    status=EXCLUDED.status,
                    started_at=EXCLUDED.started_at,
                    updated_at=EXCLUDED.updated_at,
                    current_step=EXCLUDED.current_step,
                    total_steps=EXCLUDED.total_steps,
                    progress=EXCLUDED.progress,
                    throughput_tokens_per_sec=EXCLUDED.throughput_tokens_per_sec,
                    gpu_utilization=EXCLUDED.gpu_utilization,
                    reward_latest=EXCLUDED.reward_latest,
                    loss_latest=EXCLUDED.loss_latest,
                    success_rate=EXCLUDED.success_rate,
                    anomaly_score=EXCLUDED.anomaly_score,
                    last_alert=EXCLUDED.last_alert,
                    tags_json=EXCLUDED.tags_json
                """,
                (
                    run.run_id,
                    run.name,
                    run.model_name,
                    run.trainer,
                    run.source,
                    run.status,
                    run.started_at,
                    run.updated_at,
                    run.current_step,
                    run.total_steps,
                    run.progress,
                    run.throughput_tokens_per_sec,
                    run.gpu_utilization,
                    run.reward_latest,
                    run.loss_latest,
                    run.success_rate,
                    run.anomaly_score,
                    run.last_alert,
                    json.dumps(run.tags),
                ),
            )
            self._conn.commit()

    def insert_metric(self, metric: MetricSample) -> None:
        self._insert_simple(
            "metrics",
            (
                metric.metric_id,
                metric.run_id,
                metric.metric_name,
                metric.split,
                metric.step,
                metric.timestamp,
                metric.value,
            ),
        )

    def insert_event(self, event: EventRecord) -> None:
        self._insert_simple(
            "events",
            (
                event.event_id,
                event.run_id,
                event.event_type,
                event.severity,
                event.timestamp,
                event.message,
                json.dumps(event.payload),
            ),
        )
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json")) + "\n")

    def insert_prompt(self, prompt: PromptRecord) -> None:
        self._insert_simple(
            "prompts",
            (
                prompt.prompt_id,
                prompt.run_id,
                prompt.step,
                prompt.timestamp,
                prompt.scenario,
                prompt.input_text,
                json.dumps(prompt.metadata),
            ),
        )

    def insert_output(self, output: OutputRecord) -> None:
        self._insert_simple(
            "outputs",
            (
                output.output_id,
                output.run_id,
                output.prompt_id,
                output.step,
                output.timestamp,
                output.output_text,
                output.label,
                output.score,
                json.dumps(output.metadata),
            ),
        )

    def insert_reward(self, reward: RewardRecord) -> None:
        self._insert_simple(
            "rewards",
            (
                reward.reward_id,
                reward.run_id,
                reward.step,
                reward.timestamp,
                reward.reward_total,
                json.dumps(reward.components),
            ),
        )

    def insert_alert(self, alert: AlertRecord) -> None:
        self._insert_simple(
            "alerts",
            (
                alert.alert_id,
                alert.run_id,
                alert.alert_type,
                alert.severity,
                alert.timestamp,
                alert.title,
                alert.detail,
                int(alert.resolved),
                alert.confidence,
            ),
        )

    def insert_repair(self, repair: RepairRecord) -> None:
        self._insert_simple(
            "repairs",
            (
                repair.repair_id,
                repair.run_id,
                repair.scenario_id,
                repair.timestamp,
                json.dumps(repair.failed_request),
                repair.repair_reasoning,
                json.dumps(repair.healed_request) if repair.healed_request is not None else None,
                repair.retry_result,
                repair.confidence,
                repair.outcome,
                int(repair.safe_abstained),
            ),
        )

    def _insert_simple(self, table: str, values: tuple[Any, ...]) -> None:
        placeholders = ", ".join(["%s"] * len(values))
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"INSERT INTO {table} VALUES ({placeholders}) ON CONFLICT DO NOTHING", values)
            self._conn.commit()

    def list_runs(self, *, limit: int = 20) -> list[RunRecord]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM runs ORDER BY updated_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_run_from_row(row) for row in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
        return _run_from_row(row) if row else None

    def recent_metrics(self, metric_names: list[str], *, limit_per_metric: int = 180, run_id: str | None = None) -> list[MetricSample]:
        metric_names = metric_names or ["reward"]
        samples: list[MetricSample] = []
        with self._lock, self._conn.cursor() as cur:
            for metric_name in metric_names:
                if run_id:
                    cur.execute(
                        """
                        SELECT * FROM metrics
                        WHERE metric_name = %s AND run_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """,
                        (metric_name, run_id, limit_per_metric),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM metrics
                        WHERE metric_name = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """,
                        (metric_name, limit_per_metric),
                    )
                rows = cur.fetchall()
                samples.extend(_metric_from_row(row) for row in rows)
        return list(reversed(samples))

    def recent_events(self, *, limit: int = 80, run_id: str | None = None) -> list[EventRecord]:
        with self._lock, self._conn.cursor() as cur:
            if run_id:
                cur.execute("SELECT * FROM events WHERE run_id = %s ORDER BY timestamp DESC LIMIT %s", (run_id, limit))
            else:
                cur.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_event_from_row(row) for row in rows]

    def recent_alerts(self, *, limit: int = 50) -> list[AlertRecord]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_alert_from_row(row) for row in rows]

    def recent_repairs(self, *, limit: int = 40) -> list[RepairRecord]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM repairs ORDER BY timestamp DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_repair_from_row(row) for row in rows]

    def recent_prompts_with_outputs(self, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    prompts.prompt_id,
                    prompts.run_id,
                    prompts.step,
                    prompts.timestamp,
                    prompts.scenario,
                    prompts.input_text,
                    prompts.metadata_json AS prompt_metadata_json,
                    outputs.output_id,
                    outputs.output_text,
                    outputs.label,
                    outputs.score,
                    outputs.metadata_json AS output_metadata_json
                FROM prompts
                LEFT JOIN outputs ON outputs.prompt_id = prompts.prompt_id
                ORDER BY prompts.timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            output_id = row["output_id"]
            result.append(
                {
                    "prompt_id": row["prompt_id"],
                    "run_id": row["run_id"],
                    "step": row["step"],
                    "timestamp": row["timestamp"],
                    "scenario": row["scenario"],
                    "input_text": row["input_text"],
                    "prompt_metadata": json.loads(row["prompt_metadata_json"]),
                    "output_id": output_id,
                    "output_text": row["output_text"],
                    "label": row["label"],
                    "score": row["score"],
                    "output_metadata": json.loads(row["output_metadata_json"]) if output_id else {},
                }
            )
        return result

    def recent_rewards(self, *, limit: int = 40) -> list[RewardRecord]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM rewards ORDER BY timestamp DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [
            RewardRecord(
                reward_id=row["reward_id"],
                run_id=row["run_id"],
                step=row["step"],
                timestamp=row["timestamp"],
                reward_total=row["reward_total"],
                components=json.loads(row["components_json"]),
            )
            for row in rows
        ]

    def count(self, table: str) -> int:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS count FROM {table}")
            row = cur.fetchone()
        return int(row["count"]) if row else 0

    def count_open_alerts(self) -> int:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM alerts WHERE resolved = 0")
            row = cur.fetchone()
        return int(row["count"]) if row else 0

    def table_counts(self) -> dict[str, int]:
        return {
            "runs": self.count("runs"),
            "metrics": self.count("metrics"),
            "events": self.count("events"),
            "prompts": self.count("prompts"),
            "outputs": self.count("outputs"),
            "rewards": self.count("rewards"),
            "alerts": self.count("alerts"),
            "repairs": self.count("repairs"),
        }


def _run_from_row(row: Mapping[str, Any]) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        name=row["name"],
        model_name=row["model_name"],
        trainer=row["trainer"],
        source=row["source"],
        status=row["status"],
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        current_step=row["current_step"],
        total_steps=row["total_steps"],
        progress=row["progress"],
        throughput_tokens_per_sec=row["throughput_tokens_per_sec"],
        gpu_utilization=row["gpu_utilization"],
        reward_latest=row["reward_latest"],
        loss_latest=row["loss_latest"],
        success_rate=row["success_rate"],
        anomaly_score=row["anomaly_score"],
        last_alert=row["last_alert"],
        tags=json.loads(row["tags_json"]),
    )


def _metric_from_row(row: Mapping[str, Any]) -> MetricSample:
    return MetricSample(
        metric_id=row["metric_id"],
        run_id=row["run_id"],
        metric_name=row["metric_name"],
        split=row["split"],
        step=row["step"],
        timestamp=row["timestamp"],
        value=row["value"],
    )


def _event_from_row(row: Mapping[str, Any]) -> EventRecord:
    return EventRecord(
        event_id=row["event_id"],
        run_id=row["run_id"],
        event_type=row["event_type"],
        severity=row["severity"],
        timestamp=row["timestamp"],
        message=row["message"],
        payload=json.loads(row["payload_json"]),
    )


def _alert_from_row(row: Mapping[str, Any]) -> AlertRecord:
    return AlertRecord(
        alert_id=row["alert_id"],
        run_id=row["run_id"],
        alert_type=row["alert_type"],
        severity=row["severity"],
        timestamp=row["timestamp"],
        title=row["title"],
        detail=row["detail"],
        resolved=bool(row["resolved"]),
        confidence=row["confidence"],
    )


def _repair_from_row(row: Mapping[str, Any]) -> RepairRecord:
    return RepairRecord(
        repair_id=row["repair_id"],
        run_id=row["run_id"],
        scenario_id=row["scenario_id"],
        timestamp=row["timestamp"],
        failed_request=json.loads(row["failed_request_json"]),
        repair_reasoning=row["repair_reasoning"],
        healed_request=json.loads(row["healed_request_json"]) if row["healed_request_json"] else None,
        retry_result=row["retry_result"],
        confidence=row["confidence"],
        outcome=row["outcome"],
        safe_abstained=bool(row["safe_abstained"]),
    )
