'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { MultiSeriesChart } from '@/components/charts';
import { HeroPipeline } from '@/components/hero-pipeline';
import { ErrorState, EventFeed, LoadingState, Panel, RunGrid, StatGrid } from '@/components/ui';
import { fetchJson, type PipelineOverviewResponse } from '@/lib/api';

export default function HomePage() {
  const [data, setData] = useState<PipelineOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<PipelineOverviewResponse>('/api/pipeline/overview')
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return <ErrorState label={error} />;
  }

  if (!data) {
    return <LoadingState label="Loading product overview…" />;
  }

  const totals = {
    runs: data.active_runs.length,
    events: data.recent_events.length,
    series: data.reward_series.length,
  };

  return (
    <div className="page-stack">
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-tag">
            <span className="pill">Live</span>
            Real-time AI training observability
          </span>
          <h1>
            The control plane for
            <br />
            <span className="accent">self-healing AI infrastructure.</span>
          </h1>
          <p className="lede">
            ReMorph fuses live training telemetry, persisted analytics, and an autonomous repair
            engine into a single elite observability product. See every signal. Trust every
            decision. Heal every API.
          </p>
          <div className="cta-row">
            <Link className="btn btn-primary" href="/command-center">
              Open Command Center
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </Link>
            <Link className="btn btn-secondary" href="/analytics">
              Explore Analytics
            </Link>
          </div>

          <div className="hero-stats-row">
            <div className="hero-stat">
              <strong>{totals.runs}</strong>
              <span>Active runs</span>
            </div>
            <div className="hero-stat">
              <strong>2</strong>
              <span>Live API surfaces</span>
            </div>
            <div className="hero-stat">
              <strong>{totals.events}+</strong>
              <span>Events / minute</span>
            </div>
            <div className="hero-stat">
              <strong>0ms</strong>
              <span>Setup latency</span>
            </div>
          </div>

          <div className="chip-row" style={{ marginTop: 4 }}>
            <span className="chip">Storage / Pipeline API</span>
            <span className="chip">Realtime Streaming API</span>
            <span className="chip">Anomaly intelligence</span>
            <span className="chip">Repair telemetry</span>
          </div>
        </div>

        <HeroPipeline />
      </section>

      <StatGrid stats={data.stats} />

      <section className="split-7-5">
        <Panel
          title="Live reward surface"
          description="Recent persisted reward trajectories streaming across active runs."
        >
          <MultiSeriesChart series={data.reward_series} height={300} />
        </Panel>

        <Panel
          title="Why teams pick ReMorph"
          description={data.tagline}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <FeatureRow
              title="Two production-grade API planes"
              copy="Storage / Pipeline for ingest + history. Realtime SSE for sub-second dashboards."
            />
            <FeatureRow
              title="Model-aware intelligence"
              copy="Prompts, outputs, rewards, loss spikes, and alerts are first-class citizens — not afterthoughts."
            />
            <FeatureRow
              title="Autonomous repair, observable"
              copy="ReMorph repairs are streamed in with full reasoning, confidence, and outcome telemetry."
            />
          </div>
        </Panel>
      </section>

      <section className="grid-2">
        <Panel
          title="Active run fleet"
          description="The pipeline and realtime APIs both operate over the same canonical run set."
        >
          <RunGrid runs={data.active_runs} />
        </Panel>

        <Panel
          title="Latest pipeline events"
          description="Stored events feed every analytics, alerts, and inspector view."
        >
          <EventFeed events={data.recent_events} />
        </Panel>
      </section>
    </div>
  );
}

function FeatureRow({ title, copy }: { title: string; copy: string }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '8px 1fr',
        gap: 12,
        padding: '12px 0',
        borderTop: '1px solid var(--border-soft)',
      }}
    >
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: 999,
          marginTop: 6,
          background: 'var(--grad-cool)',
          boxShadow: '0 0 12px rgba(79, 140, 255, 0.6)',
        }}
      />
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.005em' }}>
          {title}
        </div>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55 }}>
          {copy}
        </p>
      </div>
    </div>
  );
}
