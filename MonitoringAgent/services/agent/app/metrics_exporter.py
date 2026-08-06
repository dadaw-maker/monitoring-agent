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

dag_status = Gauge(
    "order_mgmt_dag_status",
    "Statut du dernier run d'un DAG Airflow individuel : 0=succès 1=échec "
    "(backs CAL-8, CAL-9, TRA-6, WMS-9 — specs.md §4 « Périmètre Airflow »)",
    ["group", "dag_id"],
    registry=registry,
)

# --------------------------------------------------------------------------
# Compteurs bruts dédiés à la maquette de tableau de bord (specs.md §8).
# Les indicateurs unitaires/chapeaux exposent des %/statuts, mais la maquette
# affiche aussi des chiffres bruts ("1 483 sur 1 522", "48 sur 50"...) qui ne
# sont pas des indicateurs en soi — ce sont ces compteurs.
# --------------------------------------------------------------------------

dashboard_essentiel = Gauge(
    "order_mgmt_dashboard_essentiel",
    "Compteurs bruts utilisés par les tuiles 'L'essentiel du jour' de la maquette (specs.md §8)",
    ["metric"],
    registry=registry,
)


def publish_dashboard_essentiel(counts: dict[str, float]) -> None:
    for metric, value in counts.items():
        if value is not None:
            dashboard_essentiel.labels(metric=metric).set(value)


def publish_unitaires(results: dict[str, IndicatorResult]) -> None:
    for result in results.values():
        labels = {"code": result.code, "type": result.type, "niveau": str(result.niveau)}
        if result.value is not None:
            indicator_value.labels(**labels).set(result.value)
        indicator_status.labels(**labels).set(result.to_prometheus_status_value())


def publish_chapeaux(results: dict[str, ChapeauResult]) -> None:
    for result in results.values():
        chapeau_status.labels(code=result.code).set(result.to_prometheus_status_value())


def publish_dag_group(group: str, data: dict | None) -> None:
    """Publishes one series per DAG in a get_airflow_dags_status() bulk result,
    so a dashboard can show which specific DAG failed, not just the group total."""
    for dag_id, state in (data or {}).get("dags", {}).items():
        dag_status.labels(group=group, dag_id=dag_id).set(0.0 if state == "success" else 1.0)
