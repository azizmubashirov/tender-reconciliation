from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or the repo-root `.env`."""

    # "../.env" covers running from backend/ (make api-dev); in containers values come from env.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: Literal["local", "staging", "pilot", "prod"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://tenderai:tenderai@localhost:5432/tenderai"
    redis_url: str = "redis://localhost:6379/0"

    # Object storage is Cloudflare R2 (S3-compatible). Without credentials files go to
    # `local_storage_dir`, which is only meant for local development.
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_bucket: str = "tenderai-dev"
    s3_region: str = "auto"
    local_storage_dir: str = "/data/storage"

    # LLM: Claude through Cloudflare AI Gateway. Without CF_* values it calls Anthropic directly.
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-opus-5-5"
    # Both CF_* and CLOUDFLARE_* names are accepted.
    cf_account_id: str | None = Field(
        None, validation_alias=AliasChoices("CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID")
    )
    cf_ai_gateway_id: str | None = Field(
        None, validation_alias=AliasChoices("CF_AI_GATEWAY_ID", "CLOUDFLARE_GATEWAY_ID")
    )
    cf_aig_token: SecretStr | None = Field(
        None, validation_alias=AliasChoices("CF_AIG_TOKEN", "CLOUDFLARE_API_TOKEN")
    )
    cf_enabled: bool | None = Field(
        None, validation_alias=AliasChoices("CF_ENABLED", "CLOUDFLARE_ENABLED")
    )

    @field_validator(
        "s3_endpoint_url", "s3_access_key_id", "s3_secret_access_key", "anthropic_api_key",
        "cf_account_id", "cf_ai_gateway_id", "cf_aig_token", "cf_enabled", mode="before",
    )  # fmt: skip
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        # docker compose passes unset variables as empty strings
        return None if value == "" else value

    @property
    def s3_configured(self) -> bool:
        return bool(self.s3_endpoint_url and self.s3_access_key_id and self.s3_secret_access_key)

    @property
    def llm_configured(self) -> bool:
        """A direct Anthropic key, or a gateway token when the key is stored in the gateway."""
        return self.anthropic_api_key is not None or (
            self.llm_base_url is not None and self.cf_aig_token is not None
        )

    @property
    def llm_base_url(self) -> str | None:
        if self.cf_enabled is not False and self.cf_account_id and self.cf_ai_gateway_id:
            return (
                f"https://gateway.ai.cloudflare.com/v1/"
                f"{self.cf_account_id}/{self.cf_ai_gateway_id}/anthropic"
            )
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
