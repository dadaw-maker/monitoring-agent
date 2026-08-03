from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8002

    # Connector modes (see ordermgmt_common.connector_mode)
    relex_mode: str = "stub"
    generix_mode: str = "stub"
    stub_seed: int | None = None

    # RELEX live connection (flux F0a — OAuth2 client credentials + API key,
    # HTTPS REST + OTLP). Populated from Azure Key Vault, see infra/keyvault.tf.
    relex_base_url: str = ""
    relex_otel_url: str = ""
    relex_oauth_token_url: str = ""
    relex_client_id: str = ""
    relex_client_secret: str = ""
    relex_api_key: str = ""

    # Generix / Infolog WMS live connection (flux F0b — interface to confirm
    # with integrator IDL, specs.md §7).
    generix_base_url: str = ""
    generix_api_key: str = ""

    http_timeout_seconds: float = 10.0


settings = Settings()
