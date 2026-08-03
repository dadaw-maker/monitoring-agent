"""Prometheus exposition for indicateurs unitaires and chapeaux.

Exposes a pull-based `/metrics` endpoint (Prometheus exposition format) on
the agent's FastAPI app. In the target Azure deployment this is scraped by
the Prometheus container app described in infra/container_apps.tf, which
Grafana then queries (specs.md §9.1, F2/F3) — remote-write to a managed
Prometheus workspace can be layered on later without touching this module.
"""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Gauge

from ordermgmt_common.models import ChapeauResult, IndicatorResult

registry = CollectorRegistry()

indicator_value = Gauge(
    "order_mgmt_indicator_value",
    "Valeur brute d'un indicateur unitaire (specs.md §6)",
    ["code", "type", "niveau"],
    registry=registry,
)

indicator_status = Gauge(
    "order_mgmt_indicator_status",
    "Statut d'un indicateur unitaire : 0=ok 1=warning 2=critical 3=unknown",
    ["code", "type", "niveau"],
    registry=registry,
)

chapeau_status = Gauge(
    "order_mgmt_chapeau_status",
    "Statut d'un indicateur chapeau (ou de tête) : 0=ok 1=warning 2=critical 3=unknown",
    ["code"],
    registry=registry,
)

poll_success = Gauge(
    "order_mgmt_poll_cycle_success",
    "1 si le dernier cycle de collecte s'est terminé sans exception, 0 sinon",
    registry=registry,
)

poll_last_timestamp = Gauge(
    "order_mgmt_poll_last_timestamp_seconds",
    "Horodatage Unix du dernier cycle de collecte",
    registry=registry,
)


def publish_unitaires(results: dict[str, IndicatorResult]) -> None:
    for result in results.values():
        labels = {"code": result.code, "type": result.type, "niveau": str(result.niveau)}
        if result.value is not None:
            indicator_value.labels(**labels).set(result.value)
        indicator_status.labels(**labels).set(result.to_prometheus_status_value())


def publish_chapeaux(results: dict[str, ChapeauResult]) -> None:
    for result in results.values():
        chapeau_status.labels(code=result.code).set(result.to_prometheus_status_value())
