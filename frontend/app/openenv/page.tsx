'use client';

import { useCallback, useEffect, useState } from 'react';

import { ErrorState, LoadingState, Panel, SectionHeader } from '@/components/ui';
import {
  fetchJson,
  fetchJsonPost,
  type OpenEnvMetaResponse,
  type OpenEnvStepResponse,
} from '@/lib/api';

const DEFAULT_ACTION = `{
  "action_type": "no_op",
  "reason": "noop from UI playground"
}`;

export default function OpenEnvPlaygroundPage() {
  const [meta, setMeta] = useState<OpenEnvMetaResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [observation, setObservation] = useState<Record<string, unknown> | null>(null);
  const [lastStep, setLastStep] = useState<OpenEnvStepResponse | null>(null);
  const [actionJson, setActionJson] = useState(DEFAULT_ACTION);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchJson<OpenEnvMetaResponse>('/api/openenv/meta')
      .then(setMeta)
      .catch((err: Error) => setLoadError(err.message));
  }, []);

  const onReset = useCallback(async (seed?: number) => {
    if (!meta?.environment_ready) return;
    setBusy(true);
    setLastStep(null);
    setActionError(null);
    try {
      const res = await fetchJsonPost<{ observation: Record<string, unknown> }>('/api/openenv/reset', {
        seed: seed ?? null,
        scenario_id: null,
      });
      setObservation(res.observation);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Reset failed');
    } finally {
      setBusy(false);
    }
  }, [meta?.environment_ready]);

  const onStep = useCallback(async () => {
    if (!meta?.environment_ready) return;
    setBusy(true);
    setActionError(null);
    try {
      let action: Record<string, unknown>;
      try {
        action = JSON.parse(actionJson) as Record<string, unknown>;
      } catch {
        throw new Error('Action JSON is invalid');
      }
      const res = await fetchJsonPost<OpenEnvStepResponse>('/api/openenv/step', { action });
      setLastStep(res);
      setObservation(res.observation as Record<string, unknown>);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Step failed');
    } finally {
      setBusy(false);
    }
  }, [meta?.environment_ready, actionJson]);

  if (loadError && !meta) {
    return <ErrorState label={loadError} />;
  }

  if (!meta) {
    return <LoadingState label="Loading OpenEnv metadata..." />;
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="OpenEnv"
        title="Interactive environment — same reset / step API as training, without Gradio."
        description="This page drives the vendored ReMorph OpenEnv (`ReMorphEnvironment`) through FastAPI. Use it for judge walkthroughs; use Command Center + Analytics for training observability."
      />

      {actionError ? (
        <Panel title="Last action failed" description="Fix JSON or reset the episode.">
          <pre className="json-preview openenv-json">{actionError}</pre>
        </Panel>
      ) : null}

      {!meta.environment_ready ? (
        <Panel title="Environment not available" description="Python cannot import remorph_openenv.">
          <p className="muted-copy">
            For local dev, set <code className="mono-inline">PYTHONPATH</code> to include{' '}
            <code className="mono-inline">remorph-openenv-submission</code>. The Docker Space sets this automatically.
          </p>
          {meta.import_error ? (
            <pre className="json-preview openenv-json" style={{ marginTop: 12 }}>
              {meta.import_error}
            </pre>
          ) : null}
        </Panel>
      ) : null}

      <section className="grid-2 wide-layout openenv-playground-grid">
        <Panel title="Controls" description="Reset samples a scenario; step applies a PolicyAction JSON.">
          <div className="openenv-actions">
            <button type="button" className="btn btn-primary" disabled={!meta.environment_ready || busy} onClick={() => onReset()}>
              Reset (random scenario)
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={!meta.environment_ready || busy}
              onClick={() => onReset(42)}
            >
              Reset seed 42
            </button>
            <button type="button" className="btn btn-primary" disabled={!meta.environment_ready || busy} onClick={() => void onStep()}>
              Step
            </button>
          </div>
          <label className="openenv-field-label" htmlFor="action-json">
            Action JSON (OpenEnv PolicyAction)
          </label>
          <textarea
            id="action-json"
            className="openenv-textarea"
            value={actionJson}
            onChange={(e) => setActionJson(e.target.value)}
            rows={12}
            spellCheck={false}
          />
          <div className="openenv-presets">
            <span className="muted-copy">Presets:</span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() =>
                setActionJson(JSON.stringify({ action_type: 'no_op', reason: 'hold' }, null, 2))
              }
            >
              no_op
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() =>
                setActionJson(
                  JSON.stringify({ action_type: 'abstain', reason: 'uncertain repair surface' }, null, 2),
                )
              }
            >
              abstain
            </button>
          </div>
          <p className="muted-copy subtle">
            Manifest: <code className="openenv-mono">remorph-openenv-submission/openenv.yaml</code>
            {' · '}
            Path: <code className="openenv-mono">{meta.submission_path ?? '—'}</code>
          </p>
        </Panel>

        <Panel title="Observation" description="Current env state after reset or step.">
          {observation && Object.keys(observation).length > 0 ? (
            <pre className="json-preview openenv-json">{JSON.stringify(observation, null, 2)}</pre>
          ) : (
            <p className="muted-copy">Call Reset to load an observation.</p>
          )}

          {lastStep ? (
            <div className="openenv-step-result glass">
              <div className="openenv-metrics">
                <span>
                  <strong>reward</strong> {lastStep.reward.toFixed(4)}
                </span>
                <span>
                  <strong>done</strong> {String(lastStep.done)}
                </span>
              </div>
              <h4 className="openenv-info-heading">info</h4>
              <pre className="json-preview">{JSON.stringify(lastStep.info, null, 2)}</pre>
            </div>
          ) : null}
        </Panel>
      </section>
    </div>
  );
}
