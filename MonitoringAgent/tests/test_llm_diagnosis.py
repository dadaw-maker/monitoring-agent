import asyncio

from conftest import import_service_module


def _chapeau(module, code, status, question="Une question ?", combined_from=None):
    from ordermgmt_common.models import ChapeauResult

    return ChapeauResult(code=code, question=question, status=status, combined_from=combined_from or [])


def test_stub_diagnosis_none_when_everything_ok():
    llm = import_service_module("agent", "llm_diagnosis")
    from ordermgmt_common.models import IndicatorStatus

    chapeaux = {"TETE": _chapeau(llm, "TETE", IndicatorStatus.OK)}
    connector = llm.StubDiagnosisConnector()
    result = asyncio.run(connector.diagnose(chapeaux, {}))
    assert result is None


def test_stub_diagnosis_mentions_worst_chapeau():
    llm = import_service_module("agent", "llm_diagnosis")
    from ordermgmt_common.models import IndicatorStatus

    chapeaux = {
        "CHAPEAU-COLLECTE": _chapeau(llm, "CHAPEAU-COLLECTE", IndicatorStatus.WARNING),
        "CHAPEAU-CALCUL": _chapeau(llm, "CHAPEAU-CALCUL", IndicatorStatus.CRITICAL),
    }
    connector = llm.StubDiagnosisConnector()
    result = asyncio.run(connector.diagnose(chapeaux, {}))
    assert result is not None
    assert "CHAPEAU-CALCUL" in result  # the CRITICAL one, not the WARNING one
    assert "[stub" in result.lower() or "stub" in result.lower()


def test_build_snapshot_text_includes_degraded_unitaires_only():
    llm = import_service_module("agent", "llm_diagnosis")
    from ordermgmt_common.models import IndicatorResult, IndicatorStatus

    chapeaux = {
        "CHAPEAU-CALCUL": _chapeau(
            llm, "CHAPEAU-CALCUL", IndicatorStatus.CRITICAL, combined_from=["CAL-1", "CAL-4"]
        ),
    }
    unitaires = {
        "CAL-1": IndicatorResult(code="CAL-1", label="Disponibilité RELEX", type="technique", niveau=1,
                                  status=IndicatorStatus.CRITICAL),
        "CAL-4": IndicatorResult(code="CAL-4", label="Propositions vs attendues", type="fonctionnel", niveau=2,
                                  status=IndicatorStatus.OK),
    }
    text = llm._build_snapshot_text(chapeaux, unitaires)
    assert "CAL-1" in text
    assert "CAL-4" not in text  # OK unitaires are not included


def test_build_diagnosis_connector_defaults_to_stub():
    llm = import_service_module("agent", "llm_diagnosis")
    connector = llm.build_diagnosis_connector()
    assert isinstance(connector, llm.StubDiagnosisConnector)
