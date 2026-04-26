# ReMorph Observability Platform

Startup-grade Hugging Face Spaces demo for ReMorph that shows real-time AI training observability, live anomaly detection, prompt/output inspection, and repair-linked API healing telemetry in one product.

## Stack

- `Next.js` static frontend export
- `FastAPI` backend API
- local `SQLite` persistence plus append-only JSONL event logs
- in-process high-frequency simulator with SSE streaming
- artifact-aware integration with the sibling `ReMorph` repository

## Local Development

### Backend

```bash
pip install -r requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 7860
```

### Frontend build

```bash
cd frontend
npm install
npm run build
```

The built frontend is exported to `frontend/out/`. The FastAPI app serves those static assets directly in local mode and from `static/` in Docker mode.

## Docker / Hugging Face Spaces

This demo is designed for a Docker Space.

Build and run locally:

```bash
docker build -t remorph-space-demo .
docker run -p 7860:7860 remorph-space-demo
```

The container serves:

- frontend pages on `/`
- backend APIs on `/api/*`
- healthcheck on `/health`

## Project Location

This demo is intended to live as a separate project at:

- `D:\HF\remorph-demo`

It reads real ReMorph artifacts from the sibling repo at:

- `D:\HF\ReMorph`

## Product Routes

- `/` executive observability landing
- `/command-center` live training command center
- `/analytics` historical analytics
- `/inspector` prompt / output inspector
- `/alerts` alerts center
- `/remorph-engine` ReMorph repair observability

## API Surfaces

### Storage / Pipeline API

- `/api/pipeline/overview`
- `/api/pipeline/runs`
- `/api/pipeline/history/analytics`
- `/api/pipeline/history/inspector`
- `/api/pipeline/alerts`
- `/api/pipeline/repairs`
- `/api/pipeline/*/ingest`

### Real-Time Streaming API

- `/api/realtime/command-center`
- `/api/realtime/system-health`
- `/api/realtime/runs/stream`
- `/api/realtime/metrics/stream`
- `/api/realtime/logs/stream`
- `/api/realtime/alerts/stream`
- `/api/realtime/repairs/stream`

## Data Sources

Current implementation uses:

- local SQLite database at `data/runtime/observability.db`
- append-only JSONL event log at `data/runtime/event_stream.jsonl`
- live in-process simulator that writes runs, metrics, prompts, outputs, rewards, alerts, and repairs
- sibling ReMorph artifacts from `../ReMorph/remorph-openenv-submission/artifacts/submission/training_run/*`
- sibling ReMorph runtime telemetry from `../ReMorph/runtime/*`

The backend is structured so these can later be replaced by:

- CSV
- JSONL telemetry
- PostgreSQL
- live FastAPI services
- streaming sources

### Storage Backend Toggle (SQLite or Postgres)

By default, backend storage is SQLite.

- `STORAGE_BACKEND=sqlite` (default)
- `STORAGE_BACKEND=postgres` (uses Postgres adapter)

For Postgres, configure either:

- `POSTGRES_DSN=postgresql://user:password@host:5432/database`

or split vars:

- `POSTGRES_HOST`
- `POSTGRES_PORT` (default `5432`)
- `POSTGRES_USER`
- `POSTGRES_PASSWORD` (optional)
- `POSTGRES_DB`
- `POSTGRES_SSLMODE` (optional, e.g. `require`)

## Test Without Docker

### 1. Install dependencies

```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. Start the backend

```bash
$env:PYTHONPATH='backend'
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 7860
```

If `7860` is already in use, either stop the old server or run on another port, for example `7861`.

To run the UI on real OpenEnv training artifacts (instead of simulator-generated data), start backend with:

```bash
$env:PYTHONPATH='backend'
$env:DATA_SOURCE_MODE='openenv'
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 7860
```

### 3. Build the frontend

```bash
cd frontend
npm run build
cd ..
```

### 4. Open the product

Visit:

- `http://127.0.0.1:7860/`
- `http://127.0.0.1:7860/command-center/`
- `http://127.0.0.1:7860/analytics/`
- `http://127.0.0.1:7860/inspector/`
- `http://127.0.0.1:7860/alerts/`
- `http://127.0.0.1:7860/remorph-engine/`

You should see:

- live charts updating inside the command center
- historical data in analytics even after page refresh
- prompt/output pairs in the inspector
- streamed alerts and repair events appearing over time

### 5. Verify persistence and streaming

Open these URLs in separate tabs:

- `http://127.0.0.1:7860/api/pipeline/overview`
- `http://127.0.0.1:7860/api/realtime/command-center`
- `http://127.0.0.1:7860/api/realtime/system-health`

You should see:

- `active_runs` populated
- `stream_rate_per_sec` above zero after startup
- new rows accumulating in `data/runtime/observability.db`
- new JSON events appending to `data/runtime/event_stream.jsonl`

### 6. Proof test for real sibling artifact integration

To prove the product is reading real ReMorph artifacts:

1. Open `http://127.0.0.1:7860/api/pipeline/repairs`
2. Confirm one of the stats reflects sibling runtime/training artifact values
3. Open `D:\HF\ReMorph\runtime` or `D:\HF\ReMorph\remorph-openenv-submission\artifacts\submission\training_run`
4. Refresh the repairs endpoint after updating artifact data
5. Confirm the stat changes after restart

### 7. Run validation checks

```bash
$env:PYTHONPATH='backend'
python -m unittest discover -s backend/tests -v

cd frontend
npm run build
```
