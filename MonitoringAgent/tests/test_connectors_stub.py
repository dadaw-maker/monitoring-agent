from conftest import import_service_module


def test_gold_stub_connector_shapes():
    connectors = import_service_module("mcp_gold", "connectors")
    gold = connectors.StubGoldConnector(seed=42)

    batch = gold.get_o4hq_batch_status()
    assert batch["source_mode"] == "stub"
    assert batch["status"] in ("completed", "running")

    sales = gold.get_store_sales_upload_status()
    assert sales["expected_stores"] == 1522
    assert sales["reported_stores"] <= sales["expected_stores"]

    wms = gold.get_wms_import_status()
    assert "cutoff_breaches" in wms
    assert wms["orders_imported"] <= wms["orders_sent"]


def test_gold_stub_is_reproducible_with_same_seed():
    connectors = import_service_module("mcp_gold", "connectors")
    a = connectors.StubGoldConnector(seed=7).get_collection_anomalies()
    b = connectors.StubGoldConnector(seed=7).get_collection_anomalies()
    assert a == b


def test_relex_and_generix_stub_connector_shapes():
    connectors = import_service_module("mcp_relex_generix", "connectors")

    relex = connectors.StubRelexConnector(seed=1)
    health = relex.get_service_health()
    assert health["status"] in ("up", "degraded")
    assert health["source_mode"] == "stub"

    generix = connectors.StubGenerixConnector(seed=1)
    direct_flow = generix.get_direct_relex_wms_flow()
    assert direct_flow["qualified"] is False  # specs.md §6.5: not qualified yet


def test_connector_mode_defaults_to_stub(monkeypatch):
    common = import_service_module("mcp_gold", "connectors")  # ensures libs/ is on sys.path
    from ordermgmt_common.connector_mode import ConnectorMode, resolve_mode

    monkeypatch.delenv("GOLD_MODE", raising=False)
    assert resolve_mode("GOLD_MODE") == ConnectorMode.STUB


def test_connector_mode_rejects_invalid_value(monkeypatch):
    import_service_module("mcp_gold", "connectors")
    from ordermgmt_common.connector_mode import resolve_mode

    monkeypatch.setenv("GOLD_MODE", "not-a-mode")
    try:
        resolve_mode("GOLD_MODE")
        assert False, "expected ValueError"
    except ValueError:
        pass
