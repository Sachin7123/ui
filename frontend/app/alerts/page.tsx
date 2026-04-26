'use client';

import { useEffect, useState } from 'react';

import { AlertFeed, ErrorState, EventFeed, LoadingState, Panel, SectionHeader, StatGrid } from '@/components/ui';
import { fetchJson, streamEvents, type AlertRecord, type AlertsResponse, type EventRecord } from '@/lib/api';

export default function AlertsPage() {
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<AlertsResponse>('/api/pipeline/alerts')
      .then((payload) => {
        setData(payload);
        setAlerts(payload.alerts);
        setEvents(payload.events);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const stopAlerts = streamEvents<AlertRecord>('/api/realtime/alerts/stream', (payload) => {
      setAlerts((current) => [payload.data, ...current].slice(0, 20));
    });
    const stopLogs = streamEvents<EventRecord>('/api/realtime/logs/stream', (payload) => {
      if (payload.data.severity === 'high' || payload.data.severity === 'critical') {
        setEvents((current) => [payload.data, ...current].slice(0, 20));
      }
    });
    return () => {
      stopAlerts();
      stopLogs();
    };
  }, []);

  if (error) {
    return <ErrorState label={error} />;
  }

  if (!data) {
    return <LoadingState label="Connecting to the alerts stream..." />;
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Alerts Center"
        title="Reward collapse, loss spikes, stalled runs, and bad generations surface here immediately."
        description="The alert engine sits between the pipeline and realtime layers, so every anomaly is both persisted and streamed live."
      />

      <StatGrid stats={data.stats} />

      <section className="grid-2 wide-layout">
        <Panel title="Live alerts" description="Direct SSE alert fanout from the realtime API.">
          <AlertFeed alerts={alerts} />
        </Panel>
        <Panel title="Critical event log" description="High-severity operational context associated with recent alerts.">
          <EventFeed events={events} />
        </Panel>
      </section>
    </div>
  );
}
