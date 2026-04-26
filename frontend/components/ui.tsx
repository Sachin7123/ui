'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

import {
  formatTimestamp,
  type AlertRecord,
  type EventRecord,
  type MetricCard,
  type RunRecord,
} from '@/lib/api';

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-header">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function Panel({
  title,
  description,
  children,
  action,
  className = '',
}: {
  title: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel glass ${className}`.trim()}>
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {action ? <div>{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

/* ---------------- Animated counter ---------------- */
function useAnimatedNumber(target: number, duration = 720) {
  const [value, setValue] = useState(target);
  const previous = useRef(target);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const start = previous.current;
    const delta = target - start;
    if (Math.abs(delta) < 0.001) {
      setValue(target);
      previous.current = target;
      return;
    }
    const startedAt = performance.now();
    const step = (now: number) => {
      const elapsed = now - startedAt;
      const t = Math.min(1, elapsed / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = start + delta * eased;
      setValue(next);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        previous.current = target;
      }
    };
    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value;
}

function formatAnimatedValue(raw: string, animated: number): string {
  const trimmed = raw.replace(/,/g, '').trim();
  const numericMatch = trimmed.match(/^-?\d+(\.\d+)?/);
  if (!numericMatch) return raw;
  const decimals = (numericMatch[1] ?? '').replace('.', '').length;
  const suffix = trimmed.slice(numericMatch[0].length);
  const formatted = animated.toLocaleString('en-US', {
    minimumFractionDigits: Math.min(decimals, 2),
    maximumFractionDigits: Math.min(decimals, 2),
  });
  return `${formatted}${suffix}`;
}

function parseNumeric(raw: string): number {
  const cleaned = raw.replace(/,/g, '').trim();
  const match = cleaned.match(/^-?\d+(\.\d+)?/);
  if (!match) return 0;
  return parseFloat(match[0]);
}

export function AnimatedNumber({ value, raw }: { value: number; raw: string }) {
  const animated = useAnimatedNumber(value);
  return <>{formatAnimatedValue(raw, animated)}</>;
}

/* ---------------- Sparkline ---------------- */
export function Sparkline({
  values,
  color = 'var(--electric-bright)',
  height = 28,
  fill = true,
}: {
  values: number[];
  color?: string;
  height?: number;
  fill?: boolean;
}) {
  const safe = values.length > 1 ? values : [0, 0];
  const min = Math.min(...safe);
  const max = Math.max(...safe);
  const range = max - min || 1;
  const points = safe
    .map((value, index) => {
      const x = (index / (safe.length - 1)) * 100;
      const y = 100 - ((value - min) / range) * 100;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');
  const id = useRef(`spark-${Math.random().toString(36).slice(2, 8)}`).current;

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      width="100%"
      height={height}
      role="img"
      aria-label="Trend sparkline"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill ? (
        <polygon
          points={`0,100 ${points} 100,100`}
          fill={`url(#${id})`}
          stroke="none"
        />
      ) : null}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ filter: `drop-shadow(0 0 6px ${color})` }}
      />
    </svg>
  );
}

/* ---------------- Stat grid (KPI cards) ---------------- */
function deriveSpark(stat: MetricCard): { values: number[]; color: string } {
  const baseValue = parseNumeric(stat.value);
  const seed = Array.from(stat.id).reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  const direction = stat.direction;
  const length = 18;
  const values: number[] = [];
  let current = baseValue * 0.65 || 1;
  for (let index = 0; index < length; index += 1) {
    const noise = Math.sin(seed + index * 0.6) * 0.08 + Math.cos(seed * 0.3 + index) * 0.05;
    const trend =
      direction === 'up' ? index * 0.045 : direction === 'down' ? -index * 0.04 : 0;
    current = current * (1 + trend / length + noise);
    values.push(current);
  }
  values.push(baseValue);
  const color =
    direction === 'up'
      ? 'var(--emerald-bright)'
      : direction === 'down'
        ? 'var(--amber-bright)'
        : 'var(--electric-bright)';
  return { values, color };
}

export function StatGrid({ stats }: { stats: MetricCard[] }) {
  return (
    <div className="stat-grid">
      {stats.map((stat) => {
        const numeric = parseNumeric(stat.value);
        const { values, color } = deriveSpark(stat);
        return (
          <article key={stat.id} className="metric-card glass">
            <div className="metric-label-row">
              <span className="metric-label">{stat.label}</span>
              <span className={`metric-delta ${stat.direction}`}>{stat.delta}</span>
            </div>
            <div className="metric-value">
              <AnimatedNumber value={numeric} raw={stat.value} />
            </div>
            <div className="metric-spark">
              <Sparkline values={values} color={color} />
            </div>
            <p className="metric-hint">{stat.hint}</p>
          </article>
        );
      })}
    </div>
  );
}

/* ---------------- Run cards ---------------- */
export function RunGrid({ runs }: { runs: RunRecord[] }) {
  return (
    <div className="run-grid">
      {runs.map((run) => (
        <article key={run.run_id} className="run-card">
          <div className="run-card-top">
            <div>
              <h4>{run.name}</h4>
              <p>
                {run.model_name} · {run.trainer}
              </p>
            </div>
            <span className={`status-pill ${run.status}`}>{run.status}</span>
          </div>
          <div className="run-progress-row">
            <span>
              {run.current_step.toLocaleString()} / {run.total_steps.toLocaleString()} steps
            </span>
            <span>{(run.progress * 100).toFixed(1)}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${run.progress * 100}%` }} />
          </div>
          <div className="run-metrics">
            <div>
              <span>Reward</span>
              <strong>{run.reward_latest.toFixed(2)}</strong>
            </div>
            <div>
              <span>Loss</span>
              <strong>{run.loss_latest.toFixed(2)}</strong>
            </div>
            <div>
              <span>GPU</span>
              <strong>{run.gpu_utilization.toFixed(0)}%</strong>
            </div>
            <div>
              <span>Tok/s</span>
              <strong>{Math.round(run.throughput_tokens_per_sec).toLocaleString()}</strong>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

/* ---------------- Event / Alert feeds ---------------- */
export function EventFeed({ events }: { events: EventRecord[] }) {
  return (
    <div className="event-feed scroll-shadow">
      {events.map((event) => (
        <article key={event.event_id} className="event-item">
          <div className={`incident-badge ${event.severity}`}>{event.severity}</div>
          <div className="event-body">
            <div className="incident-topline">
              <strong>{event.event_type}</strong>
              <span>{formatTimestamp(event.timestamp)}</span>
            </div>
            <p>{event.message}</p>
            <div className="incident-action">{event.run_id}</div>
          </div>
        </article>
      ))}
    </div>
  );
}

export function AlertFeed({ alerts }: { alerts: AlertRecord[] }) {
  return (
    <div className="alert-feed scroll-shadow">
      {alerts.map((alert) => (
        <article key={alert.alert_id} className="alert-item">
          <div className={`incident-badge ${alert.severity}`}>{alert.severity}</div>
          <div className="event-body">
            <div className="incident-topline">
              <strong>{alert.title}</strong>
              <span>{formatTimestamp(alert.timestamp)}</span>
            </div>
            <p>{alert.detail}</p>
            <div className="incident-action">
              {alert.run_id} · confidence {Math.round(alert.confidence * 100)}%
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

/* ---------------- Loading / Error ---------------- */
export function LoadingState({ label = 'Connecting to ReMorph telemetry…' }: { label?: string }) {
  return (
    <div className="loading-state">
      <div className="pulse-ring" />
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
    </div>
  );
}

export function ErrorState({ label }: { label: string }) {
  return (
    <div className="error-state">
      <strong>Unable to load data</strong>
      <p style={{ margin: 0, color: 'var(--text-muted)' }}>{label}</p>
    </div>
  );
}
