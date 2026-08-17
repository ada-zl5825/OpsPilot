from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    opspilot_env: str = "local"
    opspilot_log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://opspilot:opspilot@localhost:5432/opspilot"

    holmes_version: str = "0.39.0"
    holmes_image: str = "robustadev/holmes:0.39.0"
    holmes_base_url: str = "http://localhost:5050"
    holmes_model: str = "azure/gpt-4o"
    holmes_model_name: str = "azure-default"
    holmes_timeout_seconds: float = 180.0
    investigation_artifact_dir: str = "artifacts/investigations"
    remediation_artifact_dir: str = "artifacts/remediation"

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str | None = None

    prometheus_url: str = "http://localhost:9090"
    loki_url: str = "http://localhost:3100"
    tempo_url: str = "http://localhost:3200"

    def azure_configured(self) -> bool:
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint)


def get_settings() -> Settings:
    return Settings()
