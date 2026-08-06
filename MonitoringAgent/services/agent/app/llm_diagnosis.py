"""LLM-generated plain-language diagnosis (specs.md §11, roadmap point 1).

Runs after the chapeaux are computed each cycle, only when at least one is
not OK — never on every cycle, to keep cost and latency down. The LLM only
ever sees the snapshot this module builds from already-computed results; it
has no tool access and cannot query GOLD/RELEX/WMS itself (specs.md §9.4
"agent sans autonomie d'action" — this stays true for the LLM step too).

Stub mode (default) produces a deterministic templated sentence with no
external call, so the pipeline and dashboard/Teams wiring work end-to-end
without an API key. Live mode calls the Claude API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ordermgmt_common.models import ChapeauResult, IndicatorResult, IndicatorStatus

from .config import settings

SYSTEM_PROMPT = (
    "Tu es un assistant qui explique en français, en 2 à 3 phrases courtes, "
    "l'état d'une chaîne de supervision logistique (Order Management, "
    "LabelVie) à un exploitant technique. Base-toi strictement sur les "
    "données fournies : ne jamais inventer une cause, un chiffre ou un "
    "système qui n'y figure pas. Si la cause n'est pas déterminable à "
    "partir des données, dis-le explicitement plutôt que de spéculer."
)


def _build_snapshot_text(chapeaux: dict[str, ChapeauResult], unitaires: dict[str, IndicatorResult]) -> str:
    lines: list[str] = []
    for chapeau in chapeaux.values():
        if chapeau.status == IndicatorStatus.OK:
            continue
        lines.append(f"- {chapeau.code} [{chapeau.status.value}] — question : {chapeau.question}")
        for code in chapeau.combined_from:
            unitaire = unitaires.get(code)
            if unitaire and unitaire.status != IndicatorStatus.OK:
                lines.append(
                    f"  - {unitaire.code} ({unitaire.label}) [{unitaire.status.value}] "
                    f"valeur={unitaire.value} détail={unitaire.detail}"
                )
    return "\n".join(lines)


def _worst_chapeau(chapeaux: dict[str, ChapeauResult]) -> ChapeauResult | None:
    degraded = [c for c in chapeaux.values() if c.status != IndicatorStatus.OK]
    if not degraded:
        return None
    order = {IndicatorStatus.CRITICAL: 3, IndicatorStatus.UNKNOWN: 2, IndicatorStatus.WARNING: 1}
    return sorted(degraded, key=lambda c: order.get(c.status, 0), reverse=True)[0]


class DiagnosisConnector(ABC):
    @abstractmethod
    async def diagnose(
        self, chapeaux: dict[str, ChapeauResult], unitaires: dict[str, IndicatorResult]
    ) -> str | None:
        """Returns a short French explanation, or None if nothing is degraded."""


class StubDiagnosisConnector(DiagnosisConnector):
    async def diagnose(self, chapeaux, unitaires) -> str | None:
        worst = _worst_chapeau(chapeaux)
        if worst is None:
            return None
        return (
            f"[Mode démonstration — LLM_MODE=stub] {worst.code} est en écart "
            f"({worst.status.value}) sur la question « {worst.question} ». "
            "Ce texte est un gabarit fixe, généré sans appel à un LLM."
        )


class LiveDiagnosisConnector(DiagnosisConnector):
    def __init__(self) -> None:
        import anthropic  # imported lazily: only required when LLM_MODE=live

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def diagnose(self, chapeaux, unitaires) -> str | None:
        worst = _worst_chapeau(chapeaux)
        if worst is None:
            return None
        snapshot_text = _build_snapshot_text(chapeaux, unitaires)
        response = await self._client.messages.create(
            model=settings.llm_model,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": snapshot_text}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip() or None


def build_diagnosis_connector() -> DiagnosisConnector:
    from ordermgmt_common.connector_mode import ConnectorMode, resolve_mode

    mode = resolve_mode("LLM_MODE", ConnectorMode.STUB)
    if mode is ConnectorMode.LIVE:
        return LiveDiagnosisConnector()
    return StubDiagnosisConnector()
