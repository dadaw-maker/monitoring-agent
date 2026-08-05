"""Computation of the indicateur de tête and the 6 indicateurs chapeau (specs.md §5).

Each chapeau answers one business question by combining ("et") a small set of
unitary indicators. Combination is conservative: the chapeau is OK only if
every combined unitaire is OK; otherwise it takes the worst status among them
(CRITICAL > WARNING > UNKNOWN).
"""
from __future__ import annotations

from ordermgmt_common.models import ChapeauResult, IndicatorResult, IndicatorStatus, worst_status


def _combine(code: str, question: str, unitaires: dict[str, IndicatorResult], codes: list[str]) -> ChapeauResult:
    results = [unitaires[c] for c in codes if c in unitaires]
    if len(results) < len(codes):
        status = IndicatorStatus.UNKNOWN
    elif all(r.status == IndicatorStatus.OK for r in results):
        status = IndicatorStatus.OK
    else:
        status = worst_status(*(r.status for r in results))
    return ChapeauResult(
        code=code,
        question=question,
        status=status,
        combined_from=codes,
        detail={c: unitaires[c].status.value for c in codes if c in unitaires},
    )


def compute_tete(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "TETE",
        "Le processus a-t-il bien tourné cette nuit ?",
        unitaires,
        ["COL-2", "CAL-4", "WMS-6", "WMS-8"],
    )


def compute_chapeau_collecte(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "CHAPEAU-COLLECTE",
        "Les ventes de la nuit sont-elles toutes remontées ?",
        unitaires,
        ["COL-1", "COL-2"],
    )


def compute_chapeau_calcul(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "CHAPEAU-CALCUL",
        "Le calcul a-t-il produit une proposition pour chaque magasin ?",
        unitaires,
        ["CAL-1", "CAL-4", "CAL-6", "CAL-8"],
    )


def compute_chapeau_transmission(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "CHAPEAU-TRANSMISSION",
        "Les propositions sont-elles devenues des commandes dans GOLD ?",
        unitaires,
        ["TRA-1", "TRA-4", "TRA-6"],
    )


def compute_chapeau_depart_entrepot(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "CHAPEAU-DEPART-ENTREPOT",
        "Les commandes partiront-elles à l'entrepôt à temps ?",
        unitaires,
        ["WMS-6", "WMS-1", "WMS-8", "WMS-9"],
    )


def compute_chapeau_flux_direct(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "CHAPEAU-FLUX-DIRECT",
        "Un flux hors GOLD peut-il invalider ce constat ?",
        unitaires,
        ["DIR-1"],
    )


def compute_chapeau_tenue_chaine(unitaires: dict[str, IndicatorResult]) -> ChapeauResult:
    return _combine(
        "CHAPEAU-TENUE-CHAINE",
        "La chaîne se dégrade-t-elle dans le temps ?",
        unitaires,
        ["E2E-1", "E2E-4", "E2E-2"],
    )


def compute_all_chapeaux(unitaires: dict[str, IndicatorResult]) -> dict[str, ChapeauResult]:
    chapeaux = {
        "CHAPEAU-COLLECTE": compute_chapeau_collecte(unitaires),
        "CHAPEAU-CALCUL": compute_chapeau_calcul(unitaires),
        "CHAPEAU-TRANSMISSION": compute_chapeau_transmission(unitaires),
        "CHAPEAU-DEPART-ENTREPOT": compute_chapeau_depart_entrepot(unitaires),
        "CHAPEAU-FLUX-DIRECT": compute_chapeau_flux_direct(unitaires),
        "CHAPEAU-TENUE-CHAINE": compute_chapeau_tenue_chaine(unitaires),
    }
    chapeaux["TETE"] = compute_tete(unitaires)
    return chapeaux
