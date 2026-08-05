from conftest import import_service_module


def test_publish_dag_group_sets_one_series_per_dag():
    metrics = import_service_module("agent", "metrics_exporter")

    metrics.publish_dag_group("CAL-8", {"dags": {"dag-ok": "success", "dag-ko": "failed"}})

    ok = metrics.dag_status.labels(group="CAL-8", dag_id="dag-ok")
    ko = metrics.dag_status.labels(group="CAL-8", dag_id="dag-ko")
    assert ok._value.get() == 0.0
    assert ko._value.get() == 1.0


def test_publish_dag_group_handles_missing_data():
    metrics = import_service_module("agent", "metrics_exporter")
    # Must not raise when the MCP call failed (data is None).
    metrics.publish_dag_group("TRA-6", None)
