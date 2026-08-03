"""MCP RELEX/Generix server — read-only access to two SaaS editors (specs.md §9.1).

Deployed in Azure Container Apps, close to the editors' public APIs. Exposes
a whitelisted tool per indicator family — same "no free-form query" contract
as mcp_gold (specs.md §9.4).
"""
from __future__ import annotations

import logging

from mcp.server import MCPServer

from .config import settings
from .connectors import build_generix_connector, build_relex_connector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_relex_generix")

mcp = MCPServer("mcp-relex-generix")
relex = build_relex_connector()
generix = build_generix_connector()
logger.info(
    "mcp_relex_generix starting with RELEX_MODE=%s GENERIX_MODE=%s",
    settings.relex_mode,
    settings.generix_mode,
)


@mcp.tool()
def get_relex_service_health() -> dict:
    """RELEX service status: up / degraded / down (backs CAL-1)."""
    return relex.get_service_health()


@mcp.tool()
def get_relex_calculation_traces() -> dict:
    """Replenishment calculation traces: duration, error/timeout rate (backs CAL-2, CAL-3, CAL-5)."""
    return relex.get_calculation_traces()


@mcp.tool()
def get_relex_proposals_coverage() -> dict:
    """Proposals generated vs. expected store-article couples (backs CAL-4)."""
    return relex.get_proposals_coverage()


@mcp.tool()
def get_relex_fallback_usage() -> dict:
    """Recourse to the Reserve Order Proposals fallback (backs CAL-6, E2E-4)."""
    return relex.get_fallback_usage()


@mcp.tool()
def get_relex_proposal_anomalies() -> dict:
    """Proposals failing functional control rules (backs CAL-7)."""
    return relex.get_proposal_anomalies()


@mcp.tool()
def get_wms_service_health() -> dict:
    """WMS (Generix/Infolog) service status (backs WMS-3)."""
    return generix.get_service_health()


@mcp.tool()
def get_wms_import_duration() -> dict:
    """Time between order receipt and WMS-side integration (backs WMS-4)."""
    return generix.get_import_duration()


@mcp.tool()
def get_direct_relex_wms_flow() -> dict:
    """Status of the still-unqualified RELEX <-> WMS direct flow (backs DIR-1, DIR-2, DIR-3)."""
    return generix.get_direct_relex_wms_flow()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=settings.mcp_host, port=settings.mcp_port)
