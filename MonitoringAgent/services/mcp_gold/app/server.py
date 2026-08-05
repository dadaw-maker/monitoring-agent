"""MCP GOLD server — read-only access to GOLD (Oracle, on-premises).

Runs inside the LabelVie datacenter (specs.md §9.1). Exposes a whitelist of
tools, one per family of indicators (specs.md §9.4 "outils MCP limités par
une liste blanche") — no free-form SQL, no code execution, no filesystem
access is ever exposed to the calling agent.

Transport: streamable-http, so it can sit behind a plain HTTPS listener and
be reached by the supervision agent over the site-to-site VPN (flux F1b).
"""
from __future__ import annotations

import logging

from mcp.server import MCPServer

from .config import settings
from .connectors import build_gold_connector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_gold")

mcp = MCPServer("mcp-gold")
connector = build_gold_connector()
logger.info("mcp_gold starting with GOLD_MODE=%s", settings.gold_mode)


@mcp.tool()
def get_o4hq_batch_status() -> dict:
    """Status and end-time of the O4HQ -> GOLD nightly batch (backs COL-1)."""
    return connector.get_o4hq_batch_status()


@mcp.tool()
def get_store_sales_upload_status() -> dict:
    """Per-store sales upload completion for the reference window (backs COL-2)."""
    return connector.get_store_sales_upload_status()


@mcp.tool()
def get_stock_update_latency() -> dict:
    """Delay between a stock movement and its write in GOLD (backs COL-3)."""
    return connector.get_stock_update_latency()


@mcp.tool()
def get_collection_anomalies() -> dict:
    """Rejected/invalid rows at ingestion, by cause (backs COL-4)."""
    return connector.get_collection_anomalies()


@mcp.tool()
def get_relex_input_completeness() -> dict:
    """Store coverage and history depth ahead of the RELEX calculation (backs COL-5)."""
    return connector.get_relex_input_completeness()


@mcp.tool()
def get_stock_consistency() -> dict:
    """GOLD stock vs. physical stock count, by site (backs COL-6)."""
    return connector.get_stock_consistency()


@mcp.tool()
def get_order_proposals_reconciliation() -> dict:
    """Emitted-vs-received reconciliation for the Order Proposals flow (backs TRA-1, TRA-2)."""
    return connector.get_order_proposals_reconciliation()


@mcp.tool()
def get_interface_rejects() -> dict:
    """Technical rejects at the RELEX -> GOLD interface, by cause (backs TRA-3)."""
    return connector.get_interface_rejects()


@mcp.tool()
def get_proposal_to_order_conversion() -> dict:
    """Proposal -> order transformation rate and delay (backs TRA-4, TRA-5)."""
    return connector.get_proposal_to_order_conversion()


@mcp.tool()
def get_wms_import_status() -> dict:
    """GOLD-side view of the GOLD -> WMS import: volumes, cut-off breaches, missing fields
    (backs WMS-1, WMS-2, WMS-6, WMS-7, WMS-8)."""
    return connector.get_wms_import_status()


@mcp.tool()
def get_airflow_dag_status(dag_id: str) -> dict:
    """Last run status of a given Airflow DAG (see specs.md §4 for the DAG catalogue)."""
    return connector.get_airflow_dag_status(dag_id)


@mcp.tool()
def get_airflow_dags_status(dag_ids: list[str]) -> dict:
    """Last run status of a group of Airflow DAGs in one call (backs CAL-8, CAL-9,
    TRA-6, WMS-9 — see specs.md §4 "Périmètre Airflow" for the 43-DAG catalogue)."""
    return connector.get_airflow_dags_status(dag_ids)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=settings.mcp_host, port=settings.mcp_port)
