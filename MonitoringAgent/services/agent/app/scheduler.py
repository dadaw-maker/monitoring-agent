"""Periodic polling loop (specs.md §9.3, flux F1a/F1b: "toutes les minutes").

Each cycle: call every whitelisted MCP tool on both servers, compute the 34
indicateurs unitaires then the 7 indicateurs chapeau, publish everything to
the in-process Prometheus registry, and keep the latest snapshot in memory
for the `/indicators` debug endpoint. A failure on any single MCP call
degrades that indicator to UNKNOWN — it never aborts the cycle.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ordermgmt_common.models import ChapeauResult, IndicatorResult

from . import indicators_chapeau as chapeau
from . import indicators_unitaires as unitaires
from .config import settings
from .dashboard_essentiel import extract_essentiel_counts
from .mcp_clients import safe_call

logger = logging.getLogger("agent.scheduler")


class Snapshot:
    def __init__(self) -> None:
        self.unitaires: dict[str, IndicatorResult] = {}
        self.chapeaux: dict[str, ChapeauResult] = {}
        self.last_run_at: datetime | None = None
        self.last_run_ok: bool = False


snapshot = Snapshot()


async def _fetch_gold() -> dict[str, dict[str, Any] | None]:
    url = settings.mcp_gold_url
    names = [
        "get_o4hq_batch_status", "get_store_sales_upload_status", "get_stock_update_latency",
        "get_collection_anomalies", "get_relex_input_completeness", "get_stock_consistency",
        "get_order_proposals_reconciliation", "get_interface_rejects", "get_proposal_to_order_conversion",
        "get_wms_import_status",
    ]
    results = await asyncio.gather(*(safe_call(url, name) for name in names))
    data = dict(zip(names, results))
    data["wms_schedule_dag"] = await safe_call(url, "get_airflow_dag_status", {"dag_id": "wms-schedule-dag"})
    return data


async def _fetch_relex_generix() -> dict[str, dict[str, Any] | None]:
    url = settings.mcp_relex_generix_url
    names = [
        "get_relex_service_health", "get_relex_calculation_traces", "get_relex_proposals_coverage",
        "get_relex_fallback_usage", "get_relex_proposal_anomalies", "get_wms_service_health",
        "get_wms_import_duration", "get_direct_relex_wms_flow",
    ]
    results = await asyncio.gather(*(safe_call(url, name) for name in names))
    return dict(zip(names, results))


def _compute_unitaires(gold: dict[str, Any], rg: dict[str, Any]) -> dict[str, IndicatorResult]:
    results: dict[str, IndicatorResult] = {}

    results["COL-1"] = unitaires.compute_col_1(gold["get_o4hq_batch_status"])
    results["COL-2"] = unitaires.compute_col_2(gold["get_store_sales_upload_status"])
    results["COL-3"] = unitaires.compute_col_3(gold["get_stock_update_latency"])
    results["COL-4"] = unitaires.compute_col_4(gold["get_collection_anomalies"])
    results["COL-5"] = unitaires.compute_col_5(gold["get_relex_input_completeness"])
    results["COL-6"] = unitaires.compute_col_6(gold["get_stock_consistency"])

    results["CAL-1"] = unitaires.compute_cal_1(rg["get_relex_service_health"])
    results["CAL-2"] = unitaires.compute_cal_2(rg["get_relex_calculation_traces"])
    results["CAL-3"] = unitaires.compute_cal_3(rg["get_relex_calculation_traces"])
    results["CAL-4"] = unitaires.compute_cal_4(rg["get_relex_proposals_coverage"])
    results["CAL-5"] = unitaires.compute_cal_5(rg["get_relex_calculation_traces"])
    results["CAL-6"] = unitaires.compute_cal_6(rg["get_relex_fallback_usage"])
    results["CAL-7"] = unitaires.compute_cal_7(rg["get_relex_proposal_anomalies"])

    results["TRA-1"] = unitaires.compute_tra_1(gold["get_order_proposals_reconciliation"])
    results["TRA-2"] = unitaires.compute_tra_2(gold["get_order_proposals_reconciliation"])
    results["TRA-3"] = unitaires.compute_tra_3(gold["get_interface_rejects"])
    results["TRA-4"] = unitaires.compute_tra_4(gold["get_proposal_to_order_conversion"])
    results["TRA-5"] = unitaires.compute_tra_5(gold["get_proposal_to_order_conversion"])

    results["WMS-1"] = unitaires.compute_wms_1(gold["get_wms_import_status"])
    results["WMS-2"] = unitaires.compute_wms_2(gold["wms_schedule_dag"])
    results["WMS-3"] = unitaires.compute_wms_3(rg["get_wms_service_health"])
    results["WMS-4"] = unitaires.compute_wms_4(rg["get_wms_import_duration"])
    results["WMS-5"] = unitaires.compute_wms_5(gold["get_wms_import_status"])
    results["WMS-6"] = unitaires.compute_wms_6(gold["get_wms_import_status"])
    results["WMS-7"] = unitaires.compute_wms_7(gold["get_wms_import_status"])
    results["WMS-8"] = unitaires.compute_wms_8(gold["get_wms_import_status"])

    results["DIR-1"] = unitaires.compute_dir_1(rg["get_direct_relex_wms_flow"])
    results["DIR-2"] = unitaires.compute_dir_2(rg["get_direct_relex_wms_flow"])
    results["DIR-3"] = unitaires.compute_dir_3(rg["get_direct_relex_wms_flow"])

    results["E2E-1"] = unitaires.compute_e2e_1(results["COL-1"], results["WMS-4"])
    results["E2E-2"] = unitaires.compute_e2e_2()
    results["E2E-3"] = unitaires.compute_e2e_3(results["CAL-1"], results["WMS-3"], results["COL-1"])
    results["E2E-4"] = unitaires.compute_e2e_4(results["CAL-6"])
    results["E2E-5"] = unitaires.compute_e2e_5(results["WMS-7"])

    return results


async def run_cycle() -> None:
    from .metrics_exporter import (
        poll_last_timestamp,
        poll_success,
        publish_chapeaux,
        publish_dashboard_essentiel,
        publish_unitaires,
    )

    try:
        gold, rg = await asyncio.gather(_fetch_gold(), _fetch_relex_generix())
        unitaire_results = _compute_unitaires(gold, rg)
        chapeau_results = chapeau.compute_all_chapeaux(unitaire_results)

        publish_unitaires(unitaire_results)
        publish_chapeaux(chapeau_results)
        publish_dashboard_essentiel(extract_essentiel_counts(gold, rg))

        snapshot.unitaires = unitaire_results
        snapshot.chapeaux = chapeau_results
        snapshot.last_run_ok = True
        poll_success.set(1)
        logger.info("Poll cycle OK — %d unitaires, %d chapeaux", len(unitaire_results), len(chapeau_results))
    except Exception:  # noqa: BLE001 — a cycle must never crash the scheduler loop
        snapshot.last_run_ok = False
        poll_success.set(0)
        logger.exception("Poll cycle failed")
    finally:
        snapshot.last_run_at = datetime.now(timezone.utc)
        poll_last_timestamp.set(snapshot.last_run_at.timestamp())


async def run_forever() -> None:
    while True:
        await run_cycle()
        await asyncio.sleep(settings.poll_interval_seconds)
