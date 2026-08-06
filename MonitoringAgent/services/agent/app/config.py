from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # HTTP API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # MCP servers (flux F1a, F1b — see specs.md §9.3)
    mcp_gold_url: str = "http://mcp-gold:8001/mcp"
    mcp_relex_generix_url: str = "http://mcp-relex-generix:8002/mcp"
    mcp_call_timeout_seconds: float = 15.0

    # Scheduler (flux F1a/F1b rhythm: "toutes les minutes")
    poll_interval_seconds: int = 60

    # Thresholds — defaults from specs.md §6 where given a concrete number,
    # otherwise a conservative engineering default pending calibration
    # (specs.md marks these "à calibrer après une période d'observation").
    col3_latency_p95_warning_seconds: float = 300
    col6_stock_gap_tolerance_pct: float = 2.0
    cal2_duration_drift_warning_pct: float = 20.0
    cal5_duration_drift_warning_pct: float = 15.0
    tra2_latency_warning_seconds: float = 120
    tra5_delay_warning_seconds: float = 600
    wms4_duration_p95_warning_seconds: float = 900
    e2e1_lead_time_target_seconds: float = 6 * 3600  # objectif dashboard §8 : 6h

    # Diagnostic assisté par LLM (specs.md §11) — résume en langage naturel
    # les chapeaux en écart, à partir des indicateurs déjà calculés ce
    # cycle-ci. Ne lit ni n'écrit jamais vers GOLD/RELEX/WMS : uniquement le
    # texte produit par ce cycle (specs.md §9.4 "agent sans autonomie d'action").
    llm_mode: str = "stub"
    llm_model: str = "claude-haiku-4-5"
    anthropic_api_key: str = ""
    teams_webhook_url: str = ""

    log_level: str = "INFO"


settings = Settings()
