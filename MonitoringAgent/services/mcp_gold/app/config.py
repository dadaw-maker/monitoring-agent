from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    # Connector mode (see ordermgmt_common.connector_mode)
    gold_mode: str = "stub"
    stub_seed: int | None = None

    # Oracle live connection (populated from Azure Key Vault via Container Apps
    # secret references — never hard-coded, see infra/keyvault.tf)
    oracle_dsn: str = ""
    oracle_user: str = ""
    oracle_password: str = ""

    # Airflow REST API (flux F1d)
    airflow_base_url: str = ""
    airflow_token: str = ""


settings = Settings()
