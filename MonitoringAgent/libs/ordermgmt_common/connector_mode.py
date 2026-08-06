"""Stub/live connector selection.

Every third-party connector (Oracle GOLD, RELEX, Generix WMS) ships two
implementations behind the same interface:

- a **stub** that returns realistic, deterministic-ish fake data so the whole
  pipeline (MCP tools -> agent -> indicators -> Prometheus -> Grafana) can be
  built, deployed and demoed before real credentials exist;
- a **live** implementation that talks to the real system.

Which one is instantiated is controlled purely by an environment variable per
system (`GOLD_MODE`, `RELEX_MODE`, `GENERIX_MODE`), read at process startup.
Once real credentials are provisioned in Key Vault, flipping that env var
(and supplying the credentials) is the only change needed to point the
service at the real source — no code or image rebuild required.
"""
from __future__ import annotations

import os
from enum import Enum


class ConnectorMode(str, Enum):
    STUB = "stub"
    LIVE = "live"


def resolve_mode(env_var: str, default: ConnectorMode = ConnectorMode.STUB) -> ConnectorMode:
    raw = os.getenv(env_var, default.value).strip().lower()
    try:
        return ConnectorMode(raw)
    except ValueError as exc:
        raise ValueError(
            f"Invalid value {raw!r} for {env_var}: expected 'stub' or 'live'"
        ) from exc
