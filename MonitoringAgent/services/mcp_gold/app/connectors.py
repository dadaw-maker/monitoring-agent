"""GOLD (Oracle, on-premises) data access — stub and live implementations.

GOLD is on-premises and reached by the agent through this MCP server, which
is itself meant to run inside the LabelVie datacenter (see specs.md §9.1).
All queries are strictly read-only, against a dedicated set of views
(specs.md §9.4 "lecture seule partout").

Real view/column names are not finalized yet (specs.md §7) — `LiveGoldConnector`
is a working skeleton: connection handling and query shape are real, the
exact SQL text is marked with TODO and must be completed with the GOLD team.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings


class GoldConnector(ABC):
    """Read-only data access to GOLD, one method per family of indicators (specs.md §6)."""

    @abstractmethod
    def get_o4hq_batch_status(self) -> dict[str, Any]:
        """Backs COL-1: status/end-time of the O4HQ -> GOLD nightly batch."""

    @abstractmethod
    def get_store_sales_upload_status(self) -> dict[str, Any]:
        """Backs COL-2: per-store sales upload completion."""

    @abstractmethod
    def get_stock_update_latency(self) -> dict[str, Any]:
        """Backs COL-3: delay between a stock movement and its write in GOLD."""

    @abstractmethod
    def get_collection_anomalies(self) -> dict[str, Any]:
        """Backs COL-4: rejected/invalid rows at ingestion."""

    @abstractmethod
    def get_relex_input_completeness(self) -> dict[str, Any]:
        """Backs COL-5: store coverage / history depth ahead of the RELEX run."""

    @abstractmethod
    def get_stock_consistency(self) -> dict[str, Any]:
        """Backs COL-6: GOLD stock vs. physical stock count."""

    @abstractmethod
    def get_order_proposals_reconciliation(self) -> dict[str, Any]:
        """Backs TRA-1/TRA-2: emitted-vs-received reconciliation for Order Proposals."""

    @abstractmethod
    def get_interface_rejects(self) -> dict[str, Any]:
        """Backs TRA-3: technical rejects at the RELEX -> GOLD interface."""

    @abstractmethod
    def get_proposal_to_order_conversion(self) -> dict[str, Any]:
        """Backs TRA-4/TRA-5: proposal -> order transformation rate and delay."""

    @abstractmethod
    def get_wms_import_status(self) -> dict[str, Any]:
        """Backs WMS-1/WMS-2/WMS-6/WMS-7/WMS-8: GOLD-side view of the GOLD -> WMS import."""

    @abstractmethod
    def get_airflow_dag_status(self, dag_id: str) -> dict[str, Any]:
        """Generic DAG status lookup, used across several indicators (specs.md §4)."""


class StubGoldConnector(GoldConnector):
    """Deterministic-ish fake data, shaped like the real payloads described in specs.md §6.1-6.4."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get_o4hq_batch_status(self) -> dict[str, Any]:
        finished = self._rng.random() > 0.05
        return {
            "status": "completed" if finished else "running",
            "finished_at": (self._now() - timedelta(hours=2, minutes=19)).isoformat() if finished else None,
            "window_deadline": self._now().replace(hour=5, minute=0, second=0).isoformat(),
            "source_mode": "stub",
        }

    def get_store_sales_upload_status(self) -> dict[str, Any]:
        total_stores = 1522
        missing = self._rng.choice([0, 0, 0, 4, 12])
        return {
            "expected_stores": total_stores,
            "reported_stores": total_stores - missing,
            "missing_store_ids": [f"ST-{1000 + i}" for i in range(missing)],
            "reference_time": self._now().isoformat(),
            "source_mode": "stub",
        }

    def get_stock_update_latency(self) -> dict[str, Any]:
        return {
            "latency_seconds_p50": self._rng.uniform(30, 90),
            "latency_seconds_p95": self._rng.uniform(90, 300),
            "source_mode": "stub",
        }

    def get_collection_anomalies(self) -> dict[str, Any]:
        received = 480_000
        rejected = self._rng.randint(0, 200)
        return {
            "rows_received": received,
            "rows_rejected": rejected,
            "reject_reasons": {"format_invalide": rejected // 2, "doublon": rejected - rejected // 2},
            "source_mode": "stub",
        }

    def get_relex_input_completeness(self) -> dict[str, Any]:
        missing = self._rng.choice([0, 0, 0, 1])
        return {
            "missing_stores": missing,
            "min_history_days_required": 90,
            "min_history_days_available": 90 if missing == 0 else 45,
            "source_mode": "stub",
        }

    def get_stock_consistency(self) -> dict[str, Any]:
        return {
            "sites_checked": 40,
            "max_relative_gap_pct": round(self._rng.uniform(0, 3), 2),
            "tolerance_pct": 2.0,
            "source_mode": "stub",
        }

    def get_order_proposals_reconciliation(self) -> dict[str, Any]:
        emitted = self._rng.randint(2800, 3200)
        received = emitted - self._rng.choice([0, 0, 0, 3])
        return {
            "cycle": "03:00",
            "proposals_emitted": emitted,
            "proposals_received": received,
            "latency_seconds_p50": self._rng.uniform(20, 60),
            "source_mode": "stub",
        }

    def get_interface_rejects(self) -> dict[str, Any]:
        received = 3100
        rejected = self._rng.randint(0, 15)
        return {
            "messages_received": received,
            "messages_rejected": rejected,
            "reject_causes": {"mapping": rejected, "timeout": 0},
            "source_mode": "stub",
        }

    def get_proposal_to_order_conversion(self) -> dict[str, Any]:
        received = 3100
        converted = received - self._rng.choice([0, 0, 5])
        return {
            "proposals_received": received,
            "orders_created": converted,
            "delay_seconds_p50": self._rng.uniform(60, 300),
            "source_mode": "stub",
        }

    def get_wms_import_status(self) -> dict[str, Any]:
        sent = 3095
        imported = sent - self._rng.choice([0, 0, 2])
        cutoff_breaches = self._rng.choice([0, 0, 2])
        return {
            "orders_sent": sent,
            "orders_imported": imported,
            "orders_blocked_or_pending": self._rng.choice([0, 1, 3]),
            "cutoff_breaches": [
                {"banner": "Carrefour Hyper", "order_id": f"CMD-{9000 + i}", "cutoff": "06:30"}
                for i in range(cutoff_breaches)
            ],
            "missing_required_fields": self._rng.choice([0, 0, 1]),
            "source_mode": "stub",
        }

    def get_airflow_dag_status(self, dag_id: str) -> dict[str, Any]:
        return {
            "dag_id": dag_id,
            "last_run_state": self._rng.choice(["success", "success", "success", "failed"]),
            "last_run_end": self._now().isoformat(),
            "source_mode": "stub",
        }


# ============================================================================
# CONNEXION RÉELLE — désactivée par défaut.
#
# Pour brancher ce serveur sur le vrai GOLD (Oracle) :
#   1. `pip install oracledb` (déjà dans requirements.txt)
#   2. Décommenter la classe `LiveGoldConnector` ci-dessous
#   3. Décommenter la ligne `return LiveGoldConnector()` dans
#      `build_gold_connector()` un peu plus bas
#   4. Confirmer les noms de vues Oracle avec l'équipe GOLD (specs.md §7) et
#      les corriger dans les requêtes SELECT ci-dessous
#   5. Renseigner ORACLE_DSN / ORACLE_USER / ORACLE_PASSWORD (Key Vault en
#      prod, .env en local) et passer GOLD_MODE=live
#
# class LiveGoldConnector(GoldConnector):
#     """Real Oracle connector (python-oracledb), read-only service account.
#
#     Connection parameters come from Key Vault-backed settings (see config.py).
#     Actual view names are placeholders (specs.md §7 — "Instrumentation GOLD"
#     is still to be confirmed with the GOLD team) and must be filled in before
#     switching GOLD_MODE=live.
#     """
#
#     def __init__(self) -> None:
#         import oracledb  # imported lazily: not a hard dependency in stub mode
#
#         self._oracledb = oracledb
#         self._pool = oracledb.create_pool(
#             user=settings.oracle_user,
#             password=settings.oracle_password,
#             dsn=settings.oracle_dsn,
#             min=1,
#             max=4,
#             increment=1,
#         )
#
#     def _query_one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
#         with self._pool.acquire() as conn:
#             cursor = conn.cursor()
#             cursor.execute(sql, params or {})
#             columns = [c[0].lower() for c in cursor.description]
#             row = cursor.fetchone()
#             return dict(zip(columns, row)) if row else {}
#
#     def _query_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
#         with self._pool.acquire() as conn:
#             cursor = conn.cursor()
#             cursor.execute(sql, params or {})
#             columns = [c[0].lower() for c in cursor.description]
#             return [dict(zip(columns, row)) for row in cursor.fetchall()]
#
#     def get_o4hq_batch_status(self) -> dict[str, Any]:
#         # TODO(GOLD team): confirm the batch control-point view (specs.md §7, point 5).
#         row = self._query_one("SELECT * FROM V_SUP_O4HQ_BATCH_STATUS")
#         row["source_mode"] = "live"
#         return row
#
#     def get_store_sales_upload_status(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_STORE_SALES_UPLOAD")
#         row["source_mode"] = "live"
#         return row
#
#     def get_stock_update_latency(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_STOCK_UPDATE_LATENCY")
#         row["source_mode"] = "live"
#         return row
#
#     def get_collection_anomalies(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_COLLECTION_ANOMALIES")
#         row["source_mode"] = "live"
#         return row
#
#     def get_relex_input_completeness(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_RELEX_INPUT_COMPLETENESS")
#         row["source_mode"] = "live"
#         return row
#
#     def get_stock_consistency(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_STOCK_CONSISTENCY")
#         row["source_mode"] = "live"
#         return row
#
#     def get_order_proposals_reconciliation(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_ORDER_PROPOSALS_RECON")
#         row["source_mode"] = "live"
#         return row
#
#     def get_interface_rejects(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_INTERFACE_REJECTS")
#         row["source_mode"] = "live"
#         return row
#
#     def get_proposal_to_order_conversion(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_PROPOSAL_TO_ORDER")
#         row["source_mode"] = "live"
#         return row
#
#     def get_wms_import_status(self) -> dict[str, Any]:
#         row = self._query_one("SELECT * FROM V_SUP_WMS_IMPORT_STATUS")
#         row["source_mode"] = "live"
#         return row
#
#     def get_airflow_dag_status(self, dag_id: str) -> dict[str, Any]:
#         # TODO: confirm whether this comes from the Airflow REST API (flux F1d,
#         # port to confirm with GOLD team) rather than an Oracle view.
#         row = self._query_one("SELECT * FROM V_SUP_AIRFLOW_DAG_STATUS WHERE dag_id = :dag_id", {"dag_id": dag_id})
#         row["source_mode"] = "live"
#         return row
# ============================================================================


def build_gold_connector() -> GoldConnector:
    from ordermgmt_common.connector_mode import ConnectorMode, resolve_mode

    mode = resolve_mode("GOLD_MODE", ConnectorMode.STUB)
    if mode is ConnectorMode.LIVE:
        # Décommenter la ligne suivante une fois le bloc LiveGoldConnector
        # ci-dessus décommenté (voir instructions juste au-dessus) :
        # return LiveGoldConnector()
        raise RuntimeError(
            "GOLD_MODE=live mais LiveGoldConnector est encore commenté dans "
            "connectors.py. Décommentez le bloc 'CONNEXION RÉELLE' et la ligne "
            "'return LiveGoldConnector()' avant de redéployer (voir DEPLOYMENT.md)."
        )
    return StubGoldConnector(seed=settings.stub_seed)
