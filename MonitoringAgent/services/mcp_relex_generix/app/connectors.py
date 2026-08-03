"""RELEX and Generix/Infolog WMS data access — stub and live implementations.

Both systems are SaaS (specs.md §1 "contrainte structurante"), reached
directly from Azure over HTTPS (flux F0a / F0b). RELEX is the only system of
the whole chain natively instrumented in OpenTelemetry; the WMS interface is
still to be qualified with the integrator IDL (specs.md §7).
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings

# --------------------------------------------------------------------------
# RELEX
# --------------------------------------------------------------------------


class RelexConnector(ABC):
    @abstractmethod
    def get_service_health(self) -> dict[str, Any]:
        """Backs CAL-1: up / degraded / down, from the RELEX OTel API."""

    @abstractmethod
    def get_calculation_traces(self) -> dict[str, Any]:
        """Backs CAL-2, CAL-3, CAL-5: duration, error/timeout rate, drift."""

    @abstractmethod
    def get_proposals_coverage(self) -> dict[str, Any]:
        """Backs CAL-4: proposals generated vs. expected store-article couples."""

    @abstractmethod
    def get_fallback_usage(self) -> dict[str, Any]:
        """Backs CAL-6 / E2E-4: recourse to the Reserve Order Proposals fallback."""

    @abstractmethod
    def get_proposal_anomalies(self) -> dict[str, Any]:
        """Backs CAL-7: proposals failing functional control rules."""


class StubRelexConnector(RelexConnector):
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def get_service_health(self) -> dict[str, Any]:
        return {
            "status": self._rng.choice(["up", "up", "up", "up", "degraded"]),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source_mode": "stub",
        }

    def get_calculation_traces(self) -> dict[str, Any]:
        total_runs = 48
        errors = self._rng.choice([0, 0, 0, 1])
        return {
            "runs_total": total_runs,
            "runs_error_or_timeout": errors,
            "duration_seconds_median": self._rng.uniform(180, 260),
            "duration_seconds_reference": 220,
            "source_mode": "stub",
        }

    def get_proposals_coverage(self) -> dict[str, Any]:
        expected = 48_000
        received = expected - self._rng.choice([0, 0, 0, 480])
        return {
            "couples_expected": expected,
            "proposals_received": received,
            "source_mode": "stub",
        }

    def get_fallback_usage(self) -> dict[str, Any]:
        cycles = 3
        fallback_cycles = self._rng.choice([0, 0, 1])
        return {
            "cycles_total": cycles,
            "cycles_using_fallback": fallback_cycles,
            "fallback_duration_seconds": fallback_cycles * self._rng.uniform(60, 300),
            "source_mode": "stub",
        }

    def get_proposal_anomalies(self) -> dict[str, Any]:
        received = 47_800
        anomalies = self._rng.randint(0, 50)
        return {
            "proposals_received": received,
            "proposals_in_anomaly": anomalies,
            "anomaly_types": {"quantite_nulle": anomalies // 2, "dlc_incoherente": anomalies - anomalies // 2},
            "source_mode": "stub",
        }


class LiveRelexConnector(RelexConnector):
    """Queries the RELEX OpenTelemetry API + REST API (flux F0a).

    Authentication: OAuth2 client-credentials against `relex_oauth_token_url`,
    then bearer token + `relex_api_key` header on every call.
    """

    def __init__(self) -> None:
        import httpx

        self._httpx = httpx
        self._client = httpx.Client(base_url=settings.relex_base_url, timeout=settings.http_timeout_seconds)
        self._otel_client = httpx.Client(base_url=settings.relex_otel_url, timeout=settings.http_timeout_seconds)

    def _token(self) -> str:
        resp = self._httpx.post(
            settings.relex_oauth_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.relex_client_id,
                "client_secret": settings.relex_client_secret,
            },
            timeout=settings.http_timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}", "X-Api-Key": settings.relex_api_key}

    def get_service_health(self) -> dict[str, Any]:
        # TODO(RELEX/WZM): confirm the health-check endpoint exposed by the OTel API.
        resp = self._otel_client.get("/health", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data

    def get_calculation_traces(self) -> dict[str, Any]:
        # TODO(RELEX/WZM): confirm span/attribute names for the replenishment-calc trace.
        resp = self._otel_client.get("/traces", params={"span": "replenishment_calc"}, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data

    def get_proposals_coverage(self) -> dict[str, Any]:
        resp = self._client.get("/order-proposals/coverage", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data

    def get_fallback_usage(self) -> dict[str, Any]:
        resp = self._client.get("/order-proposals/reserve/usage", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data

    def get_proposal_anomalies(self) -> dict[str, Any]:
        # TODO(RELEX/WZM): business attributes (quantite_nulle, DLC...) still to be
        # confirmed on the span payload — see specs.md §6.2, CAL-7.
        resp = self._client.get("/order-proposals/anomalies", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data


def build_relex_connector() -> RelexConnector:
    from ordermgmt_common.connector_mode import ConnectorMode, resolve_mode

    mode = resolve_mode("RELEX_MODE", ConnectorMode.STUB)
    if mode is ConnectorMode.LIVE:
        return LiveRelexConnector()
    return StubRelexConnector(seed=settings.stub_seed)


# --------------------------------------------------------------------------
# Generix / Infolog WMS
# --------------------------------------------------------------------------


class GenerixConnector(ABC):
    @abstractmethod
    def get_service_health(self) -> dict[str, Any]:
        """Backs WMS-3: up / degraded / down, or presence of recent acknowledgements."""

    @abstractmethod
    def get_import_duration(self) -> dict[str, Any]:
        """Backs WMS-4: time between order receipt and WMS-side integration."""

    @abstractmethod
    def get_direct_relex_wms_flow(self) -> dict[str, Any]:
        """Backs DIR-1/DIR-2/DIR-3: the still-unqualified RELEX <-> WMS direct flow."""


class StubGenerixConnector(GenerixConnector):
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def get_service_health(self) -> dict[str, Any]:
        return {
            "status": self._rng.choice(["up", "up", "up", "degraded"]),
            "last_ack_at": (datetime.now(timezone.utc) - timedelta(minutes=self._rng.randint(1, 20))).isoformat(),
            "source_mode": "stub",
        }

    def get_import_duration(self) -> dict[str, Any]:
        return {
            "duration_seconds_p50": self._rng.uniform(120, 400),
            "duration_seconds_p95": self._rng.uniform(400, 900),
            "source_mode": "stub",
        }

    def get_direct_relex_wms_flow(self) -> dict[str, Any]:
        # Flow is explicitly "non qualifié à ce jour" (specs.md §6.5) — stub
        # returns an honest "unknown" shape rather than invented business data.
        return {
            "qualified": False,
            "note": "Flux RELEX<->WMS direct non qualifié — DIR-1/2/3 en attente d'atelier RELEX/IDL",
            "source_mode": "stub",
        }


class LiveGenerixConnector(GenerixConnector):
    """Real Generix/Infolog WMS connector (flux F0b).

    Interface is not confirmed yet (REST vs. SOAP/EDI — specs.md §7); this
    skeleton assumes REST/JSON and must be adjusted (e.g. swapped for a
    `zeep` SOAP client) once IDL confirms the actual protocol.
    """

    def __init__(self) -> None:
        import httpx

        self._client = httpx.Client(base_url=settings.generix_base_url, timeout=settings.http_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": settings.generix_api_key}

    def get_service_health(self) -> dict[str, Any]:
        # TODO(IDL): confirm the health/acknowledgement endpoint (specs.md §7, point 3).
        resp = self._client.get("/health", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data

    def get_import_duration(self) -> dict[str, Any]:
        resp = self._client.get("/orders/import-stats", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        data["source_mode"] = "live"
        return data

    def get_direct_relex_wms_flow(self) -> dict[str, Any]:
        # TODO(RELEX/IDL): this flow is not qualified yet — see specs.md §6.5, §7.
        raise NotImplementedError(
            "Flux direct RELEX<->WMS non qualifié : atelier RELEX/IDL requis avant "
            "d'implémenter ce connecteur live (voir specs.md §6.5 et §7)."
        )


def build_generix_connector() -> GenerixConnector:
    from ordermgmt_common.connector_mode import ConnectorMode, resolve_mode

    mode = resolve_mode("GENERIX_MODE", ConnectorMode.STUB)
    if mode is ConnectorMode.LIVE:
        return LiveGenerixConnector()
    return StubGenerixConnector(seed=settings.stub_seed)
