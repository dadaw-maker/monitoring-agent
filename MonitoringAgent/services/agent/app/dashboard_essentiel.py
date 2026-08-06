"""Raw counts needed to reproduce the dashboard maquette (specs.md §8) exactly.

The maquette shows sub-texts like "1 483 sur 1 522" or "48 sur 50" — these
are not indicateurs in their own right (specs.md §5-6), just the raw
numerator/denominator behind an existing indicateur. This module extracts
them from data already fetched during the poll cycle (no extra MCP calls).
"""
from __future__ import annotations

from typing import Any


def extract_essentiel_counts(gold: dict[str, Any], rg: dict[str, Any]) -> dict[str, float]:
    counts: dict[str, float] = {}

    sales = gold.get("get_store_sales_upload_status") or {}
    if "expected_stores" in sales:
        counts["stores_expected"] = float(sales["expected_stores"])
    if "reported_stores" in sales:
        counts["stores_reported"] = float(sales["reported_stores"])

    wms = gold.get("get_wms_import_status") or {}
    if "orders_sent" in wms:
        counts["wms_orders_sent"] = float(wms["orders_sent"])
    if "cutoff_breaches" in wms:
        counts["wms_orders_late"] = float(len(wms["cutoff_breaches"]))

    fallback = rg.get("get_relex_fallback_usage") or {}
    if "cycles_total" in fallback:
        cycles_total = fallback["cycles_total"]
        cycles_fallback = fallback.get("cycles_using_fallback", 0)
        counts["relex_cycles_total"] = float(cycles_total)
        counts["relex_cycles_nominal"] = float(cycles_total - cycles_fallback)

    rejects = gold.get("get_interface_rejects") or {}
    if "messages_rejected" in rejects:
        counts["tra_messages_rejected"] = float(rejects["messages_rejected"])

    return counts
