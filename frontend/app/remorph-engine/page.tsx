'use client';

import { useEffect, useState } from 'react';

import { ErrorState, EventFeed, LoadingState, Panel, SectionHeader, StatGrid } from '@/components/ui';
import { fetchJson, streamEvents, type EventRecord, type RemorphEngineResponse, type RepairRecord } from '@/lib/api';

export default function RemorphEnginePage() {
  const [data, setData] = useState<RemorphEngineResponse | null>(null);
  const [repairs, setRepairs] = useState<RepairRecord[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<RemorphEngineResponse>('/api/pipeline/repairs')
      .then((payload) => {
        setData(payload);
        setRepairs(payload.repairs);
        setEvents(payload.recent_events);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const stopRepairs = streamEvents<RepairRecord>('/api/realtime/repairs/stream', (payload) => {
      setRepairs((current) => [payload.data, ...current].slice(0, 12));
    });
    const stopLogs = streamEvents<EventRecord>('/api/realtime/logs/stream', (payload) => {
      if (payload.data.event_type.startsWith('repair')) {
        setEvents((current) => [payload.data, ...current].slice(0, 12));
      }
    });
    return () => {
      stopRepairs();
      stopLogs();
    };
  }, []);

  if (error) {
    return <ErrorState label={error} />;
  }

  if (!data) {
    return <LoadingState label="Loading ReMorph engine telemetry..." />;
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="ReMorph Engine"
        title="Failed request, repair reasoning, healed request, and retry result in one observability slice."
        description="This keeps the hackathon story tightly connected to training quality and alerting."
      />

      <StatGrid stats={data.stats} />

      <section className="grid-2 wide-layout">
        <Panel title="Recent repair events" description="Realtime repair and abstain outcomes generated alongside the live training stream.">
          <div className="repair-stack">
            {repairs.map((repair) => (
              <article key={repair.repair_id} className="repair-detail-card glass">
                <div className="incident-topline">
                  <strong>{repair.scenario_id}</strong>
                  <span className={`status-pill ${repair.outcome}`}>{repair.outcome}</span>
                </div>
                <div className="split-view">
                  <div className="diff-box">
                    <h4>Failed request</h4>
                    <pre className="json-preview">{JSON.stringify(repair.failed_request, null, 2)}</pre>
                  </div>
                  <div className="diff-box">
                    <h4>{repair.safe_abstained ? 'Safe abstain' : 'Healed request'}</h4>
                    <pre className="json-preview">
                      {repair.safe_abstained
                        ? JSON.stringify({ retry_result: repair.retry_result }, null, 2)
                        : JSON.stringify(repair.healed_request, null, 2)}
                    </pre>
                  </div>
                </div>
                <p className="muted-copy">{repair.repair_reasoning}</p>
              </article>
            ))}
          </div>
        </Panel>
        <Panel title="Repair event log" description="Shows the event pipeline behind the repair surfaces.">
          <EventFeed events={events} />
        </Panel>
      </section>
    </div>
  );
}
