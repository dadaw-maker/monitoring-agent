"""Agent de supervision — FastAPI entrypoint (specs.md §9.1).

Endpoints:
  GET /health      liveness/readiness probe for Azure Container Apps
  GET /metrics      Prometheus exposition (scraped by the prometheus container app)
  GET /indicators   latest computed unitaires + chapeaux, as JSON (debug / dashboard alt.)

The agent holds no direct credentials to GOLD, RELEX or Generix: it only
ever talks to the two MCP servers (specs.md §9.4 "agent sans autonomie
d'action").
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import settings
from .metrics_exporter import registry
from .scheduler import run_forever, snapshot

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("agent.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_forever())
    logger.info("Scheduler started, polling every %ss", settings.poll_interval_seconds)
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="MonitoringAgent — Order Management supervision", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "last_poll_at": snapshot.last_run_at.isoformat() if snapshot.last_run_at else None,
        "last_poll_ok": snapshot.last_run_ok,
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/indicators")
def indicators() -> JSONResponse:
    return JSONResponse(
        {
            "last_poll_at": snapshot.last_run_at.isoformat() if snapshot.last_run_at else None,
            "last_poll_ok": snapshot.last_run_ok,
            "unitaires": {code: result.model_dump(mode="json") for code, result in snapshot.unitaires.items()},
            "chapeaux": {code: result.model_dump(mode="json") for code, result in snapshot.chapeaux.items()},
        }
    )
