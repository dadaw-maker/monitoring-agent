from conftest import import_service_module

unitaires = import_service_module("agent", "indicators_unitaires")
from ordermgmt_common.models import IndicatorStatus  # noqa: E402 — path set up by import_service_module above


def test_col_1_ok_when_batch_completed():
    result = unitaires.compute_col_1({"status": "completed", "finished_at": "2026-08-03T04:41:00+00:00"})
    assert result.status == IndicatorStatus.OK
    assert result.code == "COL-1"


def test_col_1_critical_when_batch_still_running():
    result = unitaires.compute_col_1({"status": "running"})
    assert result.status == IndicatorStatus.CRITICAL


def test_col_1_unknown_when_no_data():
    result = unitaires.compute_col_1(None)
    assert result.status == IndicatorStatus.UNKNOWN


def test_col_2_full_coverage_is_ok():
    result = unitaires.compute_col_2({"expected_stores": 1522, "reported_stores": 1522})
    assert result.status == IndicatorStatus.OK
    assert result.value == 100.0


def test_col_2_missing_stores_is_not_ok():
    result = unitaires.compute_col_2({"expected_stores": 1522, "reported_stores": 1500})
    assert result.status in (IndicatorStatus.WARNING, IndicatorStatus.CRITICAL)
    assert result.value < 100.0


def test_wms_6_no_breach_is_ok():
    result = unitaires.compute_wms_6({"cutoff_breaches": []})
    assert result.status == IndicatorStatus.OK


def test_wms_6_any_breach_is_critical():
    result = unitaires.compute_wms_6({"cutoff_breaches": [{"banner": "Carrefour Hyper", "order_id": "CMD-1"}]})
    assert result.status == IndicatorStatus.CRITICAL
    assert result.value == 1.0


def test_dir_1_is_always_unknown_until_qualified():
    # specs.md §6.5: the direct RELEX<->WMS flow is explicitly unqualified.
    result = unitaires.compute_dir_1({"qualified": False})
    assert result.status == IndicatorStatus.UNKNOWN


def test_tra_1_success_when_emitted_equals_received():
    result = unitaires.compute_tra_1({"cycle": "03:00", "proposals_emitted": 100, "proposals_received": 100})
    assert result.status == IndicatorStatus.OK
    assert result.value == 0.0


def test_tra_1_critical_on_gap():
    result = unitaires.compute_tra_1({"cycle": "03:00", "proposals_emitted": 100, "proposals_received": 97})
    assert result.status == IndicatorStatus.CRITICAL
    assert result.value == 3.0


def _dags(*, ok, failed):
    dags = {f"ok-dag-{i}": "success" for i in range(ok)}
    dags.update({f"failed-dag-{i}": "failed" for i in range(failed)})
    return {"dags": dags, "source_mode": "stub"}


def test_cal_8_ok_when_all_core_dags_succeed():
    result = unitaires.compute_cal_8(_dags(ok=7, failed=0))
    assert result.status == IndicatorStatus.OK
    assert result.code == "CAL-8"


def test_cal_8_critical_on_any_failure():
    result = unitaires.compute_cal_8(_dags(ok=6, failed=1))
    assert result.status == IndicatorStatus.CRITICAL
    assert result.value == 1.0


def test_cal_8_unknown_when_no_data():
    result = unitaires.compute_cal_8(None)
    assert result.status == IndicatorStatus.UNKNOWN


def test_cal_9_warning_not_critical_on_referentiel_failure():
    # niveau 2 / moyenne priorité — a referentiel DAG failing is a trend to
    # watch, not an immediate alert (specs.md §6.2).
    result = unitaires.compute_cal_9(_dags(ok=20, failed=1))
    assert result.status == IndicatorStatus.WARNING
    assert result.value < 100.0


def test_cal_9_ok_when_all_succeed():
    result = unitaires.compute_cal_9(_dags(ok=21, failed=0))
    assert result.status == IndicatorStatus.OK
    assert result.value == 100.0


def test_tra_6_critical_on_any_failure():
    result = unitaires.compute_tra_6(_dags(ok=3, failed=1))
    assert result.status == IndicatorStatus.CRITICAL
    assert result.code == "TRA-6"


def test_wms_9_ok_when_all_interfaces_succeed():
    result = unitaires.compute_wms_9(_dags(ok=9, failed=0))
    assert result.status == IndicatorStatus.OK
    assert result.code == "WMS-9"


def test_wms_9_critical_on_any_failure():
    result = unitaires.compute_wms_9(_dags(ok=8, failed=1))
    assert result.status == IndicatorStatus.CRITICAL
