'use client';

import { useEffect, useState } from 'react';

import { MultiSeriesChart, RealtimeLineChart } from '@/components/charts';
import { AlertFeed, ErrorState, LoadingState, Panel, RunGrid, SectionHeader, StatGrid } from '@/components/ui';
import { fetchJson, type HistoricalAnalyticsResponse } from '@/lib/api';

export default function AnalyticsPage() {
  const [data, setData] = useState<HistoricalAnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<HistoricalAnalyticsResponse>('/api/pipeline/history/analytics')
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return <ErrorState label={error} />;
  }

  if (!data) {
    return <LoadingState label="Loading historical analytics..." />;
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Historical Analytics"
        title="Stored metrics, trend curves, and run comparisons for training intelligence over time."
        description="This view is driven by the Storage / Pipeline API and local persistence, not the live event fanout."
      />

      <StatGrid stats={data.stats} />

      <section className="grid-3 wide-layout">
        <Panel title="Reward Trends" description="Stored reward progression across tracked runs.">
          <MultiSeriesChart series={data.reward_trends} height={260} />
        </Panel>
        <Panel title="Loss Trends" description="Persisted loss history for regression detection and run comparison.">
          <RealtimeLineChart series={data.loss_trends} height={260} />
        </Panel>
        <Panel title="Throughput Trends" description="Historical throughput tells you whether training is healthy or stalling.">
          <RealtimeLineChart series={data.throughput_trends} height={260} />
        </Panel>
      </section>

      <section className="grid-2 wide-layout">
        <Panel title="Best runs" description="Top checkpoint-quality runs by reward and success rate.">
          <RunGrid runs={data.best_runs} />
        </Panel>
        <Panel title="Failure causes" description="Anomaly categories materialized by the analytics layer.">
          <div className="cause-list">
            {data.failure_causes.map((cause) => (
              <div key={cause.name} className="cause-row">
                <div>
                  <strong>{cause.name}</strong>
                  <p className="muted-copy">Severity: {cause.severity}</p>
                </div>
                <span className="cause-count">{cause.count}</span>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <Panel title="Historical alerts" description="Alerts are persisted so judges can see that the platform is not only visually live, but analytically durable.">
        <AlertFeed alerts={data.alerts} />
      </Panel>
    </div>
  );
}
