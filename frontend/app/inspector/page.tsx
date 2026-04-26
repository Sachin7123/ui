'use client';

import { useEffect, useState } from 'react';

import { MultiSeriesChart } from '@/components/charts';
import { ErrorState, LoadingState, Panel, SectionHeader, StatGrid } from '@/components/ui';
import { fetchJson, type InspectorResponse } from '@/lib/api';

export default function InspectorPage() {
  const [data, setData] = useState<InspectorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<InspectorResponse>('/api/pipeline/history/inspector')
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return <ErrorState label={error} />;
  }

  if (!data) {
    return <LoadingState label="Loading prompt/output inspector..." />;
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Input / Output Inspector"
        title="Inspect prompts, generations, reward assignment, and model quality at the example level."
        description="This is where judges can understand what the system saw, what the model produced, and why a reward or alert was assigned."
      />

      <StatGrid stats={data.stats} />

      <Panel title="Reward trace" description="Recent reward labels tied back to captured prompt/output events.">
        <MultiSeriesChart series={data.prompt_series} height={280} />
      </Panel>

      <div className="inspector-stack">
        {data.examples.map((example) => (
          <section key={example.prompt.prompt_id} className="grid-2 inspector-row">
            <Panel title={`Prompt · ${example.prompt.scenario}`} description={`Run ${example.prompt.run_id} · step ${example.prompt.step}`}>
              <pre className="json-preview">{example.prompt.input_text}</pre>
            </Panel>
            <Panel title={`Output · ${example.output.label}`} description={`Score ${example.output.score.toFixed(2)}`}>
              <pre className="json-preview">{example.output.output_text}</pre>
              {example.reward ? (
                <div className="detail-list" style={{ marginTop: 16 }}>
                  <div><strong>Assigned reward:</strong> {example.reward.reward_total.toFixed(2)}</div>
                  <div><strong>Components:</strong> {JSON.stringify(example.reward.components)}</div>
                </div>
              ) : null}
            </Panel>
          </section>
        ))}
      </div>
    </div>
  );
}
