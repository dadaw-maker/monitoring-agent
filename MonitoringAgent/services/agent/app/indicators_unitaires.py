"""Computation of the 34 indicateurs unitaires (specs.md §6).

Each function takes the raw dict(s) returned by one or more MCP tool calls
and turns them into an `IndicatorResult`. Thresholds come from the calling
config when specs.md gives a concrete number; where specs.md says "à
calibrer" or "à définir avec le métier", the function still runs (so the
pipeline and dashboard exist end-to-end) but documents the provisional rule
in `detail["note"]`.

Functions never raise: a missing/None input dict yields an UNKNOWN result,
never crashes the polling cycle (specs.md §9.4 "garde-fous d'exécution").
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ordermgmt_common.models import IndicatorResult, IndicatorStatus

from .config import settings


def _unknown(code: str, label: str, type_: str, niveau: int, note: str = "Donnée indisponible") -> IndicatorResult:
    return IndicatorResult(
        code=code, label=label, type=type_, niveau=niveau,
        status=IndicatorStatus.UNKNOWN, detail={"note": note}, source_mode="unknown",
    )


def _mode(data: dict[str, Any] | None) -> str:
    return (data or {}).get("source_mode", "unknown")


# --------------------------------------------------------------------------
# 6.1 Collecte des données amont (O4HQ -> GOLD)
# --------------------------------------------------------------------------

def compute_col_1(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "COL-1", "Exécution du batch nocturne O4HQ -> GOLD"
    if not data:
        return _unknown(code, label, "technique", 1)
    finished = data.get("status") == "completed"
    status = IndicatorStatus.OK if finished else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=1.0 if finished else 0.0, unit="bool", status=status,
        detail={"status": data.get("status"), "finished_at": data.get("finished_at"),
                "window_deadline": data.get("window_deadline")},
        source_mode=_mode(data),
    )


def compute_col_2(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "COL-2", "Taux de succès de remontée du Serveur Central (O4HQ)"
    if not data:
        return _unknown(code, label, "fonctionnel", 1)
    expected, reported = data.get("expected_stores", 0), data.get("reported_stores", 0)
    pct = (reported / expected * 100) if expected else 0.0
    status = IndicatorStatus.OK if pct >= 100 else (IndicatorStatus.WARNING if pct >= 99 else IndicatorStatus.CRITICAL)
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=1,
        value=round(pct, 2), unit="%", status=status,
        detail={"missing_store_ids": data.get("missing_store_ids", [])},
        source_mode=_mode(data),
    )


def compute_col_3(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "COL-3", "Latence de mise à jour du stock GOLD"
    if not data:
        return _unknown(code, label, "technique", 1)
    p95 = data.get("latency_seconds_p95", 0.0)
    status = IndicatorStatus.OK if p95 <= settings.col3_latency_p95_warning_seconds else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=p95, unit="s (p95)", status=status,
        detail={"p50": data.get("latency_seconds_p50"), "note": "Seuil provisoire, à calibrer (specs.md §6.1)"},
        source_mode=_mode(data),
    )


def compute_col_4(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "COL-4", "Anomalies et rejets à la collecte"
    if not data:
        return _unknown(code, label, "technique", 2)
    received, rejected = data.get("rows_received", 0), data.get("rows_rejected", 0)
    pct = (rejected / received * 100) if received else 0.0
    status = IndicatorStatus.OK if rejected == 0 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=2,
        value=round(pct, 4), unit="%", status=status,
        detail={"rows_rejected": rejected, "reject_reasons": data.get("reject_reasons", {}),
                "note": "Référence à établir (specs.md §6.1)"},
        source_mode=_mode(data),
    )


def compute_col_5(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "COL-5", "Complétude des données pour le calcul RELEX"
    if not data:
        return _unknown(code, label, "fonctionnel", 2)
    missing = data.get("missing_stores", 0)
    history_ok = data.get("min_history_days_available", 0) >= data.get("min_history_days_required", 0)
    status = IndicatorStatus.OK if missing == 0 and history_ok else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=float(missing), unit="magasins manquants", status=status,
        detail={"history_ok": history_ok}, source_mode=_mode(data),
    )


def compute_col_6(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "COL-6", "Cohérence stock GOLD vs stock physique"
    if not data:
        return _unknown(code, label, "fonctionnel", 2)
    gap, tolerance = data.get("max_relative_gap_pct", 0.0), data.get("tolerance_pct", settings.col6_stock_gap_tolerance_pct)
    status = IndicatorStatus.OK if gap <= tolerance else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=gap, unit="% écart max", status=status,
        detail={"tolerance_pct": tolerance, "sites_checked": data.get("sites_checked")},
        source_mode=_mode(data),
    )


# --------------------------------------------------------------------------
# 6.2 Calcul du besoin de réassort (RELEX)
# --------------------------------------------------------------------------

def compute_cal_1(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-1", "Disponibilité du service RELEX"
    if not data:
        return _unknown(code, label, "technique", 1)
    up = data.get("status") == "up"
    status = IndicatorStatus.OK if up else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=1.0 if up else 0.0, unit="bool", status=status,
        detail={"status": data.get("status")}, source_mode=_mode(data),
    )


def compute_cal_2(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-2", "Durée du calcul de réassort"
    if not data:
        return _unknown(code, label, "technique", 1)
    median, reference = data.get("duration_seconds_median", 0.0), data.get("duration_seconds_reference", 0.0)
    drift_pct = ((median - reference) / reference * 100) if reference else 0.0
    status = IndicatorStatus.OK if drift_pct <= settings.cal2_duration_drift_warning_pct else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=median, unit="s (médiane)", status=status,
        detail={"reference_seconds": reference, "drift_pct": round(drift_pct, 1)}, source_mode=_mode(data),
    )


def compute_cal_3(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-3", "Taux d'erreur ou de timeout du calcul"
    if not data:
        return _unknown(code, label, "technique", 1)
    total, errors = data.get("runs_total", 0), data.get("runs_error_or_timeout", 0)
    status = IndicatorStatus.OK if errors == 0 else IndicatorStatus.CRITICAL
    pct = (errors / total * 100) if total else 0.0
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=round(pct, 2), unit="%", status=status,
        detail={"runs_total": total, "runs_error_or_timeout": errors}, source_mode=_mode(data),
    )


def compute_cal_4(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-4", "Propositions générées vs attendues"
    if not data:
        return _unknown(code, label, "fonctionnel", 2)
    expected, received = data.get("couples_expected", 0), data.get("proposals_received", 0)
    pct = (received / expected * 100) if expected else 0.0
    status = IndicatorStatus.OK if pct >= 99.5 else (IndicatorStatus.WARNING if pct >= 95 else IndicatorStatus.CRITICAL)
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=round(pct, 2), unit="%", status=status,
        detail={"note": "Tolérance à définir avec le métier (specs.md §6.2)"}, source_mode=_mode(data),
    )


def compute_cal_5(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-5", "Durée moyenne du calcul sur la période"
    if not data:
        return _unknown(code, label, "technique", 2)
    median, reference = data.get("duration_seconds_median", 0.0), data.get("duration_seconds_reference", 0.0)
    drift_pct = ((median - reference) / reference * 100) if reference else 0.0
    status = IndicatorStatus.OK if drift_pct <= settings.cal5_duration_drift_warning_pct else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=2,
        value=median, unit="s (moyenne glissante)", status=status,
        detail={"drift_pct": round(drift_pct, 1)}, source_mode=_mode(data),
    )


def compute_cal_6(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-6", "Taux d'activation du flux de secours (Reserve Order Proposals)"
    if not data:
        return _unknown(code, label, "fonctionnel", 2)
    total, fallback = data.get("cycles_total", 0), data.get("cycles_using_fallback", 0)
    status = IndicatorStatus.OK if fallback == 0 else IndicatorStatus.WARNING
    pct = (fallback / total * 100) if total else 0.0
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=round(pct, 2), unit="% cycles", status=status,
        detail={"cycles_using_fallback": fallback, "cycles_total": total}, source_mode=_mode(data),
    )


def compute_cal_7(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "CAL-7", "Taux de propositions en anomalie fonctionnelle"
    if not data:
        return _unknown(code, label, "fonctionnel", 2, "Attributs métier à obtenir auprès de RELEX (WZM)")
    received, anomalies = data.get("proposals_received", 0), data.get("proposals_in_anomaly", 0)
    pct = (anomalies / received * 100) if received else 0.0
    status = IndicatorStatus.OK if pct == 0 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=round(pct, 3), unit="%", status=status,
        detail={"anomaly_types": data.get("anomaly_types", {}), "note": "À définir avec le métier (specs.md §6.2)"},
        source_mode=_mode(data),
    )


# --------------------------------------------------------------------------
# 6.3 Transmission RELEX -> GOLD
# --------------------------------------------------------------------------

def compute_tra_1(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "TRA-1", "Taux de succès du flux « Order Proposals »"
    if not data:
        return _unknown(code, label, "technique", 1)
    emitted, received = data.get("proposals_emitted", 0), data.get("proposals_received", 0)
    status = IndicatorStatus.OK if emitted == received else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=float(emitted - received), unit="écart (unités)", status=status,
        detail={"cycle": data.get("cycle"), "proposals_emitted": emitted, "proposals_received": received},
        source_mode=_mode(data),
    )


def compute_tra_2(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "TRA-2", "Latence de transmission unitaire"
    if not data:
        return _unknown(code, label, "technique", 1)
    p50 = data.get("latency_seconds_p50", 0.0)
    status = IndicatorStatus.OK if p50 <= settings.tra2_latency_warning_seconds else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=p50, unit="s (médiane)", status=status,
        detail={"note": "Seuil provisoire, à calibrer (specs.md §6.3)"}, source_mode=_mode(data),
    )


def compute_tra_3(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "TRA-3", "Taux de rejets techniques à l'interface"
    if not data:
        return _unknown(code, label, "technique", 2)
    received, rejected = data.get("messages_received", 0), data.get("messages_rejected", 0)
    pct = (rejected / received * 100) if received else 0.0
    status = IndicatorStatus.OK if rejected == 0 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=2,
        value=round(pct, 3), unit="%", status=status,
        detail={"reject_causes": data.get("reject_causes", {}), "note": "Référence à établir (specs.md §6.3)"},
        source_mode=_mode(data),
    )


def compute_tra_4(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "TRA-4", "Taux de transformation proposition -> commande"
    if not data:
        return _unknown(code, label, "fonctionnel", 2)
    received, converted = data.get("proposals_received", 0), data.get("orders_created", 0)
    pct = (converted / received * 100) if received else 0.0
    status = IndicatorStatus.OK if pct >= 100 else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=round(pct, 2), unit="%", status=status, detail={}, source_mode=_mode(data),
    )


def compute_tra_5(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "TRA-5", "Délai réception -> création de commande"
    if not data:
        return _unknown(code, label, "fonctionnel", 2)
    p50 = data.get("delay_seconds_p50", 0.0)
    status = IndicatorStatus.OK if p50 <= settings.tra5_delay_warning_seconds else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=p50, unit="s (médiane)", status=status,
        detail={"note": "Seuil provisoire, à calibrer (specs.md §6.3)"}, source_mode=_mode(data),
    )


# --------------------------------------------------------------------------
# 6.4 GOLD -> WMS (Infolog/Generix)
# --------------------------------------------------------------------------

def compute_wms_1(gold_data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-1", "Taux de succès de l'import WMS"
    if not gold_data:
        return _unknown(code, label, "technique", 1)
    sent, imported = gold_data.get("orders_sent", 0), gold_data.get("orders_imported", 0)
    pct = (imported / sent * 100) if sent else 0.0
    status = IndicatorStatus.OK if pct >= 100 else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=round(pct, 2), unit="%", status=status,
        detail={"orders_sent": sent, "orders_imported": imported}, source_mode=_mode(gold_data),
    )


def compute_wms_2(dag_status: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-2", "Disponibilité du canal d'échange GOLD -> WMS"
    if not dag_status:
        return _unknown(code, label, "technique", 1)
    ok = dag_status.get("last_run_state") == "success"
    status = IndicatorStatus.OK if ok else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=1.0 if ok else 0.0, unit="bool", status=status,
        detail={"dag_id": dag_status.get("dag_id"), "last_run_state": dag_status.get("last_run_state")},
        source_mode=_mode(dag_status),
    )


def compute_wms_3(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-3", "Disponibilité du service WMS"
    if not data:
        return _unknown(code, label, "technique", 1, "Interface à qualifier avec l'intégrateur IDL (specs.md §7)")
    up = data.get("status") == "up"
    status = IndicatorStatus.OK if up else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=1.0 if up else 0.0, unit="bool", status=status,
        detail={"status": data.get("status"), "last_ack_at": data.get("last_ack_at")}, source_mode=_mode(data),
    )


def compute_wms_4(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-4", "Durée du traitement d'import côté WMS"
    if not data:
        return _unknown(code, label, "technique", 1, "Instrumentation côté WMS à obtenir (specs.md §7)")
    p95 = data.get("duration_seconds_p95", 0.0)
    status = IndicatorStatus.OK if p95 <= settings.wms4_duration_p95_warning_seconds else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=p95, unit="s (p95)", status=status,
        detail={"p50": data.get("duration_seconds_p50")}, source_mode=_mode(data),
    )


def compute_wms_5(gold_data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-5", "Taux d'erreur ou de timeout de l'import WMS"
    if not gold_data:
        return _unknown(code, label, "technique", 1)
    sent, imported = gold_data.get("orders_sent", 0), gold_data.get("orders_imported", 0)
    errors = max(sent - imported, 0)
    status = IndicatorStatus.OK if errors == 0 else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        value=float(errors), unit="messages en erreur", status=status,
        detail={"note": "Approximation à partir du différentiel GOLD envoyé/importé (WMS-1)"},
        source_mode=_mode(gold_data),
    )


def compute_wms_6(gold_data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-6", "Respect des règles de cut-off par enseigne"
    if not gold_data:
        return _unknown(code, label, "fonctionnel", 1)
    breaches = gold_data.get("cutoff_breaches", [])
    status = IndicatorStatus.OK if not breaches else IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=1,
        value=float(len(breaches)), unit="commandes après cut-off", status=status,
        detail={"breaches": breaches, "note": "Paramétrage des cut-off à récupérer (specs.md §6.4)"},
        source_mode=_mode(gold_data),
    )


def compute_wms_7(gold_data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-7", "Taux de commandes bloquées ou en attente côté WMS"
    if not gold_data:
        return _unknown(code, label, "fonctionnel", 2)
    blocked = gold_data.get("orders_blocked_or_pending", 0)
    status = IndicatorStatus.OK if blocked == 0 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=float(blocked), unit="commandes", status=status,
        detail={"note": "Seuil à définir avec l'exploitation (specs.md §6.4)"}, source_mode=_mode(gold_data),
    )


def compute_wms_8(gold_data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "WMS-8", "Complétude des données transmises"
    if not gold_data:
        return _unknown(code, label, "fonctionnel", 2)
    missing = gold_data.get("missing_required_fields", 0)
    status = IndicatorStatus.OK if missing == 0 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=float(missing), unit="messages avec champ manquant", status=status, detail={},
        source_mode=_mode(gold_data),
    )


# --------------------------------------------------------------------------
# 6.5 Flux direct RELEX <-> WMS
# --------------------------------------------------------------------------

def compute_dir_1(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "DIR-1", "Disponibilité et fiabilité du flux direct RELEX <-> WMS"
    qualified = bool(data and data.get("qualified"))
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1,
        status=IndicatorStatus.UNKNOWN,
        detail={"note": (data or {}).get("note", "Flux non qualifié — priorité n°1 (specs.md §6.5, §7)"),
                "qualified": qualified},
        source_mode=_mode(data),
    )


def compute_dir_2(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "DIR-2", "Nature et contenu des données échangées"
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        status=IndicatorStatus.UNKNOWN,
        detail={"note": "Livrable de cartographie — atelier RELEX/IDL requis (specs.md §6.5)"},
        source_mode=_mode(data),
    )


def compute_dir_3(data: dict[str, Any] | None) -> IndicatorResult:
    code, label = "DIR-3", "Volume et fréquence du flux"
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=2,
        status=IndicatorStatus.UNKNOWN,
        detail={"note": "Sans objet à ce stade — flux non qualifié (specs.md §6.5)"},
        source_mode=_mode(data),
    )


# --------------------------------------------------------------------------
# 6.6 Indicateurs de bout en bout
# --------------------------------------------------------------------------

def compute_e2e_1(col_1: IndicatorResult, wms_4: IndicatorResult) -> IndicatorResult:
    code, label = "E2E-1", "Lead time global (collecte -> ordre WMS)"
    finished_at = (col_1.detail or {}).get("finished_at")
    if not finished_at or wms_4.value is None:
        return _unknown(code, label, "fonctionnel", 2, "Corrélation inter-systèmes requise (specs.md §7)")
    try:
        start = datetime.fromisoformat(finished_at)
    except ValueError:
        return _unknown(code, label, "fonctionnel", 2)
    lead_time = (datetime.now(start.tzinfo) - start).total_seconds()
    status = IndicatorStatus.OK if lead_time <= settings.e2e1_lead_time_target_seconds else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=lead_time, unit="s", status=status,
        detail={"target_seconds": settings.e2e1_lead_time_target_seconds,
                "note": "Approximation batch->import ; décomposition par étape à affiner"},
        source_mode="derived",
    )


def compute_e2e_2() -> IndicatorResult:
    code, label = "E2E-2", "Traçabilité de l'identifiant de proposition RELEX"
    return _unknown(code, label, "technique", 1, "Identifiant de corrélation trans-systèmes non implémenté (specs.md §7)")


def compute_e2e_3(cal_1: IndicatorResult, wms_3: IndicatorResult, col_1: IndicatorResult) -> IndicatorResult:
    code, label = "E2E-3", "Disponibilité simultanée de RELEX, GOLD et WMS"
    statuses = [cal_1.status, wms_3.status, col_1.status]
    if IndicatorStatus.UNKNOWN in statuses:
        status = IndicatorStatus.UNKNOWN
    elif all(s == IndicatorStatus.OK for s in statuses):
        status = IndicatorStatus.OK
    else:
        status = IndicatorStatus.CRITICAL
    return IndicatorResult(
        code=code, label=label, type="technique", niveau=1, status=status,
        detail={"relex": cal_1.status.value, "wms": wms_3.status.value, "gold": col_1.status.value},
        source_mode="derived",
    )


def compute_e2e_4(cal_6: IndicatorResult) -> IndicatorResult:
    code, label = "E2E-4", "Taux de cycles nominaux sans recours au secours"
    if cal_6.status == IndicatorStatus.UNKNOWN:
        return _unknown(code, label, "fonctionnel", 2)
    nominal_pct = 100.0 - (cal_6.value or 0.0)
    status = IndicatorStatus.OK if nominal_pct >= 100 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=round(nominal_pct, 2), unit="% cycles nominaux", status=status,
        detail={}, source_mode="derived",
    )


def compute_e2e_5(wms_7: IndicatorResult) -> IndicatorResult:
    code, label = "E2E-5", "Taux d'incidents nécessitant une intervention manuelle"
    if wms_7.status == IndicatorStatus.UNKNOWN:
        return _unknown(code, label, "fonctionnel", 2)
    status = IndicatorStatus.OK if (wms_7.value or 0.0) == 0 else IndicatorStatus.WARNING
    return IndicatorResult(
        code=code, label=label, type="fonctionnel", niveau=2,
        value=wms_7.value, unit="commandes bloquées (proxy)", status=status,
        detail={"note": "Approximation via WMS-7 en attendant une source d'incidents déclarés (specs.md §7)"},
        source_mode="derived",
    )
