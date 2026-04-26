from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.repositories.base import demo_root
from app.models import (
    IngestEventsRequest,
    IngestMetricsRequest,
    IngestOutputsRequest,
    IngestPromptsRequest,
    IngestRepairsRequest,
    IngestRewardsRequest,
)
from app.services.demo_service import DemoService

app = FastAPI(title="ReMorph Observability Platform API", version="0.2.0")
service = DemoService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_default_static_root = Path(__file__).resolve().parents[2] / "static"
STATIC_ROOT = (
    _default_static_root
    if _default_static_root.exists()
    else demo_root() / "frontend" / "out"
)


@app.on_event("startup")
def startup() -> None:
    service.start()


@app.on_event("shutdown")
def shutdown() -> None:
    service.stop()


@app.get("/health")
def healthcheck():
    return {"status": "ok", "message": "observability-platform-running"}


@app.get("/api/pipeline/overview")
def pipeline_overview():
    return service.pipeline_overview()


@app.get("/api/pipeline/runs")
def pipeline_runs(page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100)):
    return service.list_runs(page=page, page_size=page_size)


@app.get("/api/pipeline/history/analytics")
def pipeline_analytics():
    return service.historical_analytics()


@app.get("/api/pipeline/history/inspector")
def pipeline_inspector(limit: int = Query(12, ge=1, le=50)):
    return service.inspector(limit=limit)


@app.get("/api/pipeline/alerts")
def pipeline_alerts(limit: int = Query(24, ge=1, le=100)):
    return service.alerts_center(limit=limit)


@app.get("/api/pipeline/repairs")
def pipeline_repairs(limit: int = Query(12, ge=1, le=100)):
    return service.remorph_engine(limit=limit)


@app.post("/api/pipeline/metrics/ingest")
def ingest_metrics(payload: IngestMetricsRequest):
    return service.ingest_metrics(payload)


@app.post("/api/pipeline/events/ingest")
def ingest_events(payload: IngestEventsRequest):
    return service.ingest_events(payload)


@app.post("/api/pipeline/prompts/ingest")
def ingest_prompts(payload: IngestPromptsRequest):
    return service.ingest_prompts(payload)


@app.post("/api/pipeline/outputs/ingest")
def ingest_outputs(payload: IngestOutputsRequest):
    return service.ingest_outputs(payload)


@app.post("/api/pipeline/rewards/ingest")
def ingest_rewards(payload: IngestRewardsRequest):
    return service.ingest_rewards(payload)


@app.post("/api/pipeline/repairs/ingest")
def ingest_repairs(payload: IngestRepairsRequest):
    return service.ingest_repairs(payload)


@app.get("/api/realtime/command-center")
def realtime_command_center():
    return service.command_center()


@app.get("/api/realtime/system-health")
def realtime_system_health():
    return service.system_health()


def _stream_channel(channel: str, once: bool = False):
    async def event_generator():
        channel_queue = service.subscribe(channel)
        try:
            while True:
                payload = await asyncio.to_thread(channel_queue.get)
                yield f"data: {json.dumps(payload.model_dump(mode='json'))}\n\n"
                if once:
                    break
        finally:
            service.unsubscribe(channel, channel_queue)

    return event_generator()


@app.get("/api/realtime/runs/stream")
async def realtime_runs_stream(once: bool = Query(False)):
    return StreamingResponse(
        _stream_channel("runs", once=once), media_type="text/event-stream"
    )


@app.get("/api/realtime/metrics/stream")
async def realtime_metrics_stream(once: bool = Query(False)):
    return StreamingResponse(
        _stream_channel("metrics", once=once), media_type="text/event-stream"
    )


@app.get("/api/realtime/logs/stream")
async def realtime_logs_stream(once: bool = Query(False)):
    return StreamingResponse(
        _stream_channel("logs", once=once), media_type="text/event-stream"
    )


@app.get("/api/realtime/alerts/stream")
async def realtime_alerts_stream(once: bool = Query(False)):
    return StreamingResponse(
        _stream_channel("alerts", once=once), media_type="text/event-stream"
    )


@app.get("/api/realtime/repairs/stream")
async def realtime_repairs_stream(once: bool = Query(False)):
    return StreamingResponse(
        _stream_channel("repairs", once=once), media_type="text/event-stream"
    )


@app.get("/api/realtime/all/stream")
async def realtime_all_stream(once: bool = Query(False)):
    async def multiplex():
        while True:
            payload = service.command_center().model_dump(mode="json")
            yield f"data: {json.dumps({'channel': 'snapshot', 'event_type': 'command_center.snapshot', 'timestamp': payload['generated_at'], 'data': payload})}\n\n"
            if once:
                break
            await asyncio.sleep(1)

    return StreamingResponse(multiplex(), media_type="text/event-stream")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    if full_path.startswith("api/") or full_path == "health":
        return JSONResponse({"detail": "Not found"}, status_code=404)

    requested = full_path.strip("/")
    candidates = []
    if requested:
        candidates.extend(
            [
                STATIC_ROOT / requested,
                STATIC_ROOT / requested / "index.html",
                STATIC_ROOT / f"{requested}.html",
            ]
        )
    candidates.append(STATIC_ROOT / "index.html")

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)

    raise HTTPException(status_code=404, detail="Frontend asset not found")
