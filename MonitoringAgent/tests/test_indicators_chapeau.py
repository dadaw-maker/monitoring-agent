from conftest import import_service_module

chapeau = import_service_module("agent", "indicators_chapeau")
from ordermgmt_common.models import IndicatorResult, IndicatorStatus  # noqa: E402


def _result(code: str, status: IndicatorStatus) -> IndicatorResult:
    return IndicatorResult(code=code, label=code, type="technique", niveau=1, status=status)


def test_tete_ok_when_all_combined_ok():
    unitaires = {
        "COL-2": _result("COL-2", IndicatorStatus.OK),
        "CAL-4": _result("CAL-4", IndicatorStatus.OK),
        "WMS-6": _result("WMS-6", IndicatorStatus.OK),
        "WMS-8": _result("WMS-8", IndicatorStatus.OK),
    }
    tete = chapeau.compute_tete(unitaires)
    assert tete.status == IndicatorStatus.OK
    assert tete.combined_from == ["COL-2", "CAL-4", "WMS-6", "WMS-8"]


def test_tete_critical_if_one_combined_is_critical():
    unitaires = {
        "COL-2": _result("COL-2", IndicatorStatus.OK),
        "CAL-4": _result("CAL-4", IndicatorStatus.OK),
        "WMS-6": _result("WMS-6", IndicatorStatus.CRITICAL),
        "WMS-8": _result("WMS-8", IndicatorStatus.OK),
    }
    tete = chapeau.compute_tete(unitaires)
    assert tete.status == IndicatorStatus.CRITICAL


def test_tete_unknown_when_a_unitaire_is_missing():
    unitaires = {
        "COL-2": _result("COL-2", IndicatorStatus.OK),
        "CAL-4": _result("CAL-4", IndicatorStatus.OK),
        "WMS-6": _result("WMS-6", IndicatorStatus.OK),
        # WMS-8 missing
    }
    tete = chapeau.compute_tete(unitaires)
    assert tete.status == IndicatorStatus.UNKNOWN


def test_chapeau_flux_direct_stays_unknown_pending_qualification():
    unitaires = {"DIR-1": _result("DIR-1", IndicatorStatus.UNKNOWN)}
    result = chapeau.compute_chapeau_flux_direct(unitaires)
    assert result.status == IndicatorStatus.UNKNOWN


def test_compute_all_chapeaux_returns_seven_entries():
    unitaires = {code: _result(code, IndicatorStatus.OK) for code in [
        "COL-1", "COL-2", "CAL-1", "CAL-4", "CAL-6", "TRA-1", "TRA-4",
        "WMS-6", "WMS-1", "WMS-8", "DIR-1", "E2E-1", "E2E-4", "E2E-2",
    ]}
    all_chapeaux = chapeau.compute_all_chapeaux(unitaires)
    assert len(all_chapeaux) == 7
    assert "TETE" in all_chapeaux
    assert all(r.status == IndicatorStatus.OK for r in all_chapeaux.values())
