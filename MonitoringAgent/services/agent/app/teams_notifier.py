"""Posts the LLM diagnosis to Teams (specs.md §11).

Separate from Grafana's own threshold-based Teams alert
(monitoring/grafana/provisioning/alerting/contactpoints.yaml) — that one
still fires immediately on a raw status change. This one follows a few
seconds later, on the same webhook, with the readable "why" once the LLM
diagnosis is ready. Never raises: a failed Teams post must not fail the
poll cycle.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger("agent.teams_notifier")


async def post_diagnosis(text: str) -> None:
    if not settings.teams_webhook_url or settings.teams_webhook_url == "changeme":
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.teams_webhook_url, json={"text": text})
            response.raise_for_status()
    except Exception:  # noqa: BLE001 — a notification failure must never break the poll cycle
        logger.exception("Failed to post LLM diagnosis to Teams")
