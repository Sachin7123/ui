"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { MultiSeriesChart, RealtimeLineChart } from "@/components/charts";
import {
  AlertFeed,
  AnimatedNumber,
  ErrorState,
  EventFeed,
  LoadingState,
  Panel,
  RunGrid,
  SectionHeader,
  StatGrid,
} from "@/components/ui";
import {
  fetchJson,
  formatTimestamp,
  streamEvents,
  type AlertRecord,
  type CommandCenterResponse,
  type EventRecord,
  type RepairRecord,
  type SystemHealthResponse,
} from "@/lib/api";

type RailItem = {
  id: string;
  kind: "log" | "alert" | "repair";
  title: string;
  detail: string;
  timestamp: string;
  severityClass: string;
};

type ActivityCounters = {
  metricSnapshots: number;
  logs: number;
  alerts: number;
  repairs: number;
};

type StreamStatus = "connecting" | "live" | "reconnecting";

const HEATMAP_BUCKETS = 60;
const SNAPSHOT_THROTTLE_MS = 600;
const STALE_STREAM_MS = 4000;

export default function CommandCenterPage() {
  const [data, setData] = useState<CommandCenterResponse | null>(null);
  const [logs, setLogs] = useState<EventRecord[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [repairs, setRepairs] = useState<RepairRecord[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(
    null,
  );
  const [railItems, setRailItems] = useState<RailItem[]>([]);
  const [activity, setActivity] = useState<ActivityCounters>({
    metricSnapshots: 0,
    logs: 0,
    alerts: 0,
    repairs: 0,
  });
  const [activityBuckets, setActivityBuckets] = useState<number[]>(() =>
    new Array(HEATMAP_BUCKETS).fill(0),
  );
  const [latestRepair, setLatestRepair] = useState<RepairRecord | null>(null);
  const [latestRepairTick, setLatestRepairTick] = useState(0);
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const [clockTick, setClockTick] = useState(Date.now());
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("connecting");
  const [error, setError] = useState<string | null>(null);

  const lastSnapshotAppliedRef = useRef(0);
  const lastEventReceivedAtRef = useRef<number>(0);
  const bucketCounterRef = useRef(0);
  const errorCountRef = useRef({ metrics: 0, logs: 0, alerts: 0, repairs: 0 });

  useEffect(() => {
    fetchJson<CommandCenterResponse>("/api/realtime/command-center")
      .then((payload) => {
        setData(payload);
        setLogs(payload.logs);
        setAlerts(payload.alerts);
        setRepairs(payload.repairs);
        setRailItems(
          buildInitialRail(payload.logs, payload.alerts, payload.repairs),
        );
        if (payload.repairs.length > 0) {
          setLatestRepair(payload.repairs[0]);
          setLatestRepairTick((tick) => tick + 1);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const pollHealth = () => {
      fetchJson<SystemHealthResponse>("/api/realtime/system-health")
        .then((payload) => {
          if (cancelled) {
            return;
          }
          setSystemHealth(payload);
        })
        .catch(() => {
          if (!cancelled) {
            setStreamStatus("reconnecting");
          }
        });
    };

    const noteEvent = () => {
      lastEventReceivedAtRef.current = Date.now();
      bucketCounterRef.current += 1;
      setStreamStatus("live");
    };

    const rotateBuckets = () => {
      setActivityBuckets((current) => {
        const next = current.slice(1);
        next.push(bucketCounterRef.current);
        bucketCounterRef.current = 0;
        return next;
      });
      const since = Date.now() - lastEventReceivedAtRef.current;
      if (lastEventReceivedAtRef.current > 0 && since > STALE_STREAM_MS) {
        setStreamStatus("reconnecting");
      }
    };

    pollHealth();
    const pollId = window.setInterval(pollHealth, 2200);
    const clockId = window.setInterval(() => setClockTick(Date.now()), 1000);
    const bucketId = window.setInterval(rotateBuckets, 1000);

    const unsubscribers = [
      streamEvents<CommandCenterResponse>("/api/realtime/metrics/stream", {
        onMessage: (payload) => {
          if (payload.event_type !== "command_center.snapshot") {
            return;
          }
          noteEvent();
          setLastEventAt(payload.timestamp);
          setActivity((current) => ({
            ...current,
            metricSnapshots: current.metricSnapshots + 1,
          }));

          const now = Date.now();
          if (now - lastSnapshotAppliedRef.current < SNAPSHOT_THROTTLE_MS) {
            return;
          }
          lastSnapshotAppliedRef.current = now;
          setData(payload.data);
        },
        onError: () => {
          errorCountRef.current.metrics += 1;
          setStreamStatus("reconnecting");
        },
      }),
      streamEvents<EventRecord>("/api/realtime/logs/stream", {
        onMessage: (payload) => {
          noteEvent();
          setLastEventAt(payload.timestamp);
          setLogs((current) => [payload.data, ...current].slice(0, 16));
          setActivity((current) => ({ ...current, logs: current.logs + 1 }));
          setRailItems((current) =>
            prependRailItem(current, {
              id: payload.data.event_id,
              kind: "log",
              title: payload.data.event_type,
              detail: payload.data.message,
              timestamp: payload.data.timestamp,
              severityClass: payload.data.severity,
            }),
          );
        },
        onError: () => {
          errorCountRef.current.logs += 1;
          setStreamStatus("reconnecting");
        },
      }),
      streamEvents<AlertRecord>("/api/realtime/alerts/stream", {
        onMessage: (payload) => {
          noteEvent();
          setLastEventAt(payload.timestamp);
          setAlerts((current) => [payload.data, ...current].slice(0, 10));
          setActivity((current) => ({
            ...current,
            alerts: current.alerts + 1,
          }));
          setRailItems((current) =>
            prependRailItem(current, {
              id: payload.data.alert_id,
              kind: "alert",
              title: payload.data.title,
              detail: payload.data.detail,
              timestamp: payload.data.timestamp,
              severityClass: payload.data.severity,
            }),
          );
        },
        onError: () => {
          errorCountRef.current.alerts += 1;
          setStreamStatus("reconnecting");
        },
      }),
      streamEvents<RepairRecord>("/api/realtime/repairs/stream", {
        onMessage: (payload) => {
          noteEvent();
          setLastEventAt(payload.timestamp);
          setRepairs((current) => [payload.data, ...current].slice(0, 10));
          setActivity((current) => ({
            ...current,
            repairs: current.repairs + 1,
          }));
          setLatestRepair(payload.data);
          setLatestRepairTick((tick) => tick + 1);
          setRailItems((current) =>
            prependRailItem(current, {
              id: payload.data.repair_id,
              kind: "repair",
              title: payload.data.scenario_id,
              detail: payload.data.retry_result,
              timestamp: payload.data.timestamp,
              severityClass:
                payload.data.outcome === "success"
                  ? "medium"
                  : payload.data.outcome === "abstained"
                    ? "high"
                    : "critical",
            }),
          );
        },
        onError: () => {
          errorCountRef.current.repairs += 1;
          setStreamStatus("reconnecting");
        },
      }),
    ];
    return () => {
      cancelled = true;
      window.clearInterval(pollId);
      window.clearInterval(clockId);
      window.clearInterval(bucketId);
      unsubscribers.forEach((unsubscribe) => unsubscribe());
    };
  }, []);

  const tickerItems = useMemo(() => railItems.slice(0, 12), [railItems]);

  if (error) {
    return <ErrorState label={error} />;
  }

  if (!data) {
    return <LoadingState label="Connecting to the realtime training stream…" />;
  }

  const statusTone =
    streamStatus === "live"
      ? "success"
      : streamStatus === "reconnecting"
        ? "warning"
        : "neutral";
  const lastPulse = describeLastEvent(lastEventAt, clockTick);
  const activityTiles = [
    {
      id: "metricSnapshots",
      label: "Snapshot pushes",
      value: activity.metricSnapshots,
      hint: "Live metric snapshots merged into the dashboard.",
    },
    {
      id: "logs",
      label: "Log events",
      value: activity.logs,
      hint: "Structured runtime events received this session.",
    },
    {
      id: "alerts",
      label: "Alert fanout",
      value: activity.alerts,
      hint: "Anomaly signals streamed directly from the engine.",
    },
    {
      id: "repairs",
      label: "Repair updates",
      value: activity.repairs,
      hint: "Repair-linked learning signals rendered in real time.",
    },
  ];

  return (
    <div className="page-stack">
      <LiveTicker items={tickerItems} />

      {streamStatus === "reconnecting" ? (
        <DegradedBanner lastPulse={lastPulse} />
      ) : null}

      <SectionHeader
        eyebrow="Live Training Command Center"
        title="Instant visibility into every training pulse, checkpoint, alert, and repair event."
        description="This page combines live SSE updates with persisted analytics so judges can understand the whole system in seconds."
        action={
          <div className="chip">
            Updated {formatTimestamp(data.generated_at)}
          </div>
        }
      />

      <StatGrid stats={data.stats} />

      <section className="grid-3 wide-layout">
        <Panel
          title="Realtime stream status"
          description="Live connection health across the SSE surfaces and storage pipeline."
        >
          <div className="stream-status-card">
            <div className="stream-status-top">
              <div className={`signal-pill ${statusTone}`}>
                <span className="signal-dot" />
                {streamStatus === "live"
                  ? "Live"
                  : streamStatus === "reconnecting"
                    ? "Reconnecting"
                    : "Connecting"}
              </div>
              <div className="muted-copy">{lastPulse}</div>
            </div>
            <div className="stream-metrics">
              <div>
                <span>Ingest/sec</span>
                <strong>
                  <AnimatedNumber
                    value={systemHealth?.ingest_rate_per_sec ?? 0}
                    raw={`${(systemHealth?.ingest_rate_per_sec ?? 0).toFixed(1)}`}
                  />
                </strong>
              </div>
              <div>
                <span>Stream/sec</span>
                <strong>
                  <AnimatedNumber
                    value={systemHealth?.stream_rate_per_sec ?? 0}
                    raw={`${(systemHealth?.stream_rate_per_sec ?? 0).toFixed(1)}`}
                  />
                </strong>
              </div>
              <div>
                <span>Queue depth</span>
                <strong>
                  <AnimatedNumber
                    value={systemHealth?.queue_depth ?? 0}
                    raw={`${systemHealth?.queue_depth ?? 0}`}
                  />
                </strong>
              </div>
              <div>
                <span>Storage ms</span>
                <strong>
                  <AnimatedNumber
                    value={systemHealth?.storage_latency_ms ?? 0}
                    raw={`${(systemHealth?.storage_latency_ms ?? 0).toFixed(1)}`}
                  />
                </strong>
              </div>
            </div>
            <ActivityHeatmap buckets={activityBuckets} />
          </div>
        </Panel>

        <Panel
          title="Channel activity"
          description="Session-local counters that prove the dashboard is truly streaming, not just polling charts."
          className="channel-panel"
        >
          <div className="channel-activity-grid">
            {activityTiles.map((tile) => (
              <article key={tile.id} className="channel-card">
                <div className="channel-card-label">{tile.label}</div>
                <div className="channel-card-value">
                  <AnimatedNumber value={tile.value} raw={`${tile.value}`} />
                </div>
                <p>{tile.hint}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel
          title="Live event rail"
          description="A fast event lane for recent logs, alerts, and repair outcomes."
          action={<div className="chip">{railItems.length} recent events</div>}
        >
          <div className="event-rail">
            {railItems.map((item, index) => (
              <article
                key={`${item.kind}-${item.id}-${item.timestamp}-${index}`}
                className="rail-item"
              >
                <div className={`incident-badge ${item.severityClass}`}>
                  {item.kind}
                </div>
                <div className="rail-item-body">
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
                <span>{formatTimestamp(item.timestamp)}</span>
              </article>
            ))}
          </div>
        </Panel>
      </section>

      {latestRepair ? (
        <LiveRepairPulse repair={latestRepair} tick={latestRepairTick} />
      ) : null}

      <section className="grid-2 wide-layout">
        <Panel
          title="Active runs"
          description="Each run streams reward, loss, throughput, and anomaly score into the command center."
        >
          <RunGrid runs={data.active_runs} />
        </Panel>
        <Panel
          title="Live GPU utilization"
          description="Aggregate GPU pressure across the active fleet."
        >
          <RealtimeLineChart series={data.gpu_series} height={300} />
        </Panel>
      </section>

      <section className="grid-3 wide-layout">
        <Panel title="Reward" description="Realtime reward movement by run.">
          <MultiSeriesChart series={data.reward_series} height={260} />
        </Panel>
        <Panel
          title="Loss"
          description="Observe spikes, collapse, and recovery instantly."
        >
          <RealtimeLineChart series={data.loss_series} height={260} />
        </Panel>
        <Panel
          title="Throughput"
          description="Token throughput and training velocity in one view."
        >
          <RealtimeLineChart series={data.throughput_series} height={260} />
        </Panel>
      </section>

      <section className="grid-2 wide-layout">
        <Panel
          title="Realtime logs"
          description="Structured log stream emitted directly from the training simulator and realtime API."
        >
          <EventFeed events={logs} />
        </Panel>
        <Panel
          title="Alerts"
          description="Reward collapse, loss spikes, stalled runs, and bad generations surface here first."
        >
          <AlertFeed alerts={alerts} />
        </Panel>
      </section>

      <Panel
        title="Repair-linked learning events"
        description="Shows the ReMorph engine side of the observability product."
      >
        <div className="repair-timeline">
          {repairs.map((repair) => (
            <article
              key={repair.repair_id}
              className="repair-card glass live-repair-card"
            >
              <div className="incident-topline">
                <strong>{repair.scenario_id}</strong>
                <span className={`status-pill ${repair.outcome}`}>
                  {repair.outcome}
                </span>
              </div>
              <div className="repair-flow">
                <div className="repair-step done">
                  <span>1</span>
                  Detect
                </div>
                <div className="repair-step done">
                  <span>2</span>
                  Analyze
                </div>
                <div
                  className={`repair-step ${repair.safe_abstained ? "warning" : "done"}`}
                >
                  <span>3</span>
                  {repair.safe_abstained ? "Abstain" : "Patch"}
                </div>
                <div
                  className={`repair-step ${
                    repair.outcome === "success"
                      ? "success"
                      : repair.outcome === "failed"
                        ? "critical"
                        : "warning"
                  }`}
                >
                  <span>4</span>
                  Retry
                </div>
              </div>
              <p>{repair.repair_reasoning}</p>
              <div className="repair-meta">
                <div className="incident-action">{repair.retry_result}</div>
                <div className="incident-action">
                  confidence {Math.round(repair.confidence * 100)}%
                </div>
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}

/* ----------------------------------------------------------------------- */
/* Live ticker                                                             */
/* ----------------------------------------------------------------------- */
function LiveTicker({ items }: { items: RailItem[] }) {
  if (items.length === 0) {
    return null;
  }
  const sequence =
    items.length < 6 ? [...items, ...items, ...items] : [...items, ...items];
  return (
    <div className="live-ticker" aria-label="Live event ticker">
      <div className="live-ticker-tag">
        <span className="signal-dot" />
        Live feed
      </div>
      <div className="live-ticker-track">
        <div className="live-ticker-strip">
          {sequence.map((item, index) => (
            <span className="live-ticker-item" key={`${item.id}-${index}`}>
              <span className={`incident-badge ${item.severityClass}`}>
                {item.kind}
              </span>
              <strong>{item.title}</strong>
              <em>{item.detail}</em>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------- */
/* Activity heatmap (60 second rolling buckets)                            */
/* ----------------------------------------------------------------------- */
function ActivityHeatmap({ buckets }: { buckets: number[] }) {
  const max = Math.max(1, ...buckets);
  return (
    <div
      className="activity-heatmap"
      aria-label="Per-second event activity (last 60s)"
    >
      <div className="activity-heatmap-strip">
        {buckets.map((value, index) => {
          const intensity = Math.min(1, value / max);
          const opacity = value === 0 ? 0.15 : 0.25 + intensity * 0.75;
          return (
            <span
              key={index}
              className="activity-cell"
              style={{
                background: `rgba(79, 140, 255, ${opacity.toFixed(2)})`,
                boxShadow:
                  value > 0
                    ? `0 0 6px rgba(79, 140, 255, ${(intensity * 0.6).toFixed(2)})`
                    : "none",
              }}
              title={`${value} events`}
            />
          );
        })}
      </div>
      <div className="activity-heatmap-legend">
        <span>60s ago</span>
        <span>now</span>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------- */
/* Live repair pulse line                                                  */
/* ----------------------------------------------------------------------- */
function LiveRepairPulse({
  repair,
  tick,
}: {
  repair: RepairRecord;
  tick: number;
}) {
  const tone =
    repair.outcome === "success"
      ? "success"
      : repair.outcome === "abstained"
        ? "warning"
        : "critical";
  return (
    <section key={tick} className="live-repair-pulse glass">
      <div className="live-repair-head">
        <div className="eyebrow">Last repair pulse</div>
        <h3>{repair.scenario_id}</h3>
        <p>{repair.repair_reasoning}</p>
      </div>
      <div className="live-repair-track">
        <svg viewBox="0 0 800 80" preserveAspectRatio="none" aria-hidden>
          <defs>
            <linearGradient
              id="pulse-gradient"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop offset="0%" stopColor="rgba(251, 113, 133, 0.6)" />
              <stop offset="50%" stopColor="rgba(139, 92, 246, 0.85)" />
              <stop offset="100%" stopColor="rgba(52, 211, 153, 0.85)" />
            </linearGradient>
            <filter id="pulse-glow">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>
          <path
            d="M 8 40 C 200 -10, 400 90, 600 40 S 780 60, 792 40"
            fill="none"
            stroke="url(#pulse-gradient)"
            strokeWidth="2.5"
            filter="url(#pulse-glow)"
          />
          <path
            d="M 8 40 C 200 -10, 400 90, 600 40 S 780 60, 792 40"
            fill="none"
            stroke="white"
            strokeWidth="1.4"
            strokeDasharray="6 800"
            className="pulse-particle-path"
          />
        </svg>
        <div className="live-repair-stages">
          <span className="repair-step done">
            <span>1</span>
            Failed
          </span>
          <span className="repair-step done">
            <span>2</span>
            Analyzed
          </span>
          <span
            className={`repair-step ${repair.safe_abstained ? "warning" : "done"}`}
          >
            <span>3</span>
            {repair.safe_abstained ? "Abstained" : "Patched"}
          </span>
          <span className={`repair-step ${tone}`}>
            <span>4</span>
            {repair.outcome.charAt(0).toUpperCase() + repair.outcome.slice(1)}
          </span>
        </div>
      </div>
      <div className="live-repair-foot">
        <div className="incident-action">{repair.retry_result}</div>
        <div className="incident-action">
          confidence {Math.round(repair.confidence * 100)}%
        </div>
        <div className="incident-action">
          {formatTimestamp(repair.timestamp)}
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------------- */
/* Degraded stream banner                                                  */
/* ----------------------------------------------------------------------- */
function DegradedBanner({ lastPulse }: { lastPulse: string }) {
  return (
    <div className="degraded-banner" role="alert">
      <div className="degraded-banner-mark">
        <span className="signal-dot" />
      </div>
      <div className="degraded-banner-body">
        <strong>Stream degraded</strong>
        <p>
          SSE updates have paused. We will reconnect automatically. {lastPulse}.
        </p>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------- */
/* Helpers                                                                 */
/* ----------------------------------------------------------------------- */
function buildInitialRail(
  logs: EventRecord[],
  alerts: AlertRecord[],
  repairs: RepairRecord[],
): RailItem[] {
  const logItems: RailItem[] = logs.map((item) => ({
    id: item.event_id,
    kind: "log",
    title: item.event_type,
    detail: item.message,
    timestamp: item.timestamp,
    severityClass: item.severity,
  }));
  const alertItems: RailItem[] = alerts.map((item) => ({
    id: item.alert_id,
    kind: "alert",
    title: item.title,
    detail: item.detail,
    timestamp: item.timestamp,
    severityClass: item.severity,
  }));
  const repairItems: RailItem[] = repairs.map((item) => ({
    id: item.repair_id,
    kind: "repair",
    title: item.scenario_id,
    detail: item.retry_result,
    timestamp: item.timestamp,
    severityClass:
      item.outcome === "success"
        ? "medium"
        : item.outcome === "abstained"
          ? "high"
          : "critical",
  }));

  return [...logItems, ...alertItems, ...repairItems]
    .sort(
      (left, right) =>
        new Date(right.timestamp).getTime() -
        new Date(left.timestamp).getTime(),
    )
    .slice(0, 18);
}

function describeLastEvent(lastEventAt: string | null, nowMs: number): string {
  if (!lastEventAt) {
    return "Waiting for first event";
  }

  const ageMs = Math.max(0, nowMs - new Date(lastEventAt).getTime());
  if (ageMs < 1500) {
    return "Last event < 1s ago";
  }
  if (ageMs < 60_000) {
    return `Last event ${Math.round(ageMs / 1000)}s ago`;
  }
  return `Last event ${Math.round(ageMs / 60_000)}m ago`;
}

function prependRailItem(current: RailItem[], item: RailItem): RailItem[] {
  return [item, ...current].slice(0, 18);
}
