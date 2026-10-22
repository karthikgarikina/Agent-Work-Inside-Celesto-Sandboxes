import os
from typing import Any
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    celesto_provider: str = Field(default="cloud", alias="CELESTO_PROVIDER")
    celesto_api_key: str = Field(default="replace-me", alias="CELESTO_API_KEY")
    celesto_backend: str = Field(default="firecracker", alias="CELESTO_BACKEND")
    celesto_template_id: str = Field(default="scratch", alias="CELESTO_TEMPLATE_ID")

    llm_base_url: str = Field(default="https://example-llm-host/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="replace-me", alias="LLM_API_KEY")
    llm_model: str = Field(default="replace-with-a-model-name", alias="LLM_MODEL")

    database_url: str = Field(
        default="postgresql://ledger:ledger@ledger:5432/ledger",
        alias="DATABASE_URL",
    )
    api_port: int = Field(default=8080, alias="API_PORT")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")

    audit_log_path: str = Field(default="logs/commands.jsonl", alias="AUDIT_LOG_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("api_port", mode="before")
    @classmethod
    def parse_api_port(cls, v: Any) -> int:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 8080
        try:
            return int(v)
        except Exception:
            return 8080

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
