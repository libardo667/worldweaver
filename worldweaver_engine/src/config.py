# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = None if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("PYTEST_VERSION") else ".env"


class Settings(BaseSettings):
    """System-wide configuration settings."""

    # LLM Settings
    llm_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemini-3-flash-preview"
    embedding_model: str = "openai/text-embedding-3-small"

    llm_temperature: float = 0.7
    llm_max_tokens: int = 2500
    llm_timeout_seconds: int = 30
    llm_retries: int = 2
    llm_frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    llm_presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    llm_city_builder_model: Optional[str] = Field(
        default=None,
        validation_alias="LLM_CITY_BUILDER_MODEL",
    )

    # Cache & Performance
    state_manager_cache_max_size: int = 500
    state_manager_cache_ttl_seconds: int = 3600
    session_consistency_mode: str = Field(
        default="cache",
        validation_alias="WW_SESSION_CONSISTENCY_MODE",
    )

    # World state settings
    enable_world_graph_extraction: bool = True
    enable_world_projection: bool = True
    enable_dev_reset: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_DEV_RESET",
    )

    # Shard / Federation Settings
    city_id: str = Field(default="san_francisco", validation_alias="CITY_ID")
    shard_id: Optional[str] = Field(default=None, validation_alias="SHARD_ID")
    shard_type: str = Field(default="city", validation_alias="SHARD_TYPE")  # "city" | "world" | "neighborhood"
    federation_url: Optional[str] = Field(default=None, validation_alias="FEDERATION_URL")
    federation_pulse_interval: int = Field(default=300, validation_alias="FEDERATION_PULSE_INTERVAL_SECONDS")
    city_db_file: str = Field(default="worldweaver.db", validation_alias="CITY_DB_FILE")
    federation_token: Optional[str] = Field(default=None, validation_alias="FEDERATION_TOKEN")
    public_url: Optional[str] = Field(default=None, validation_alias="WW_PUBLIC_URL")
    shard_experience_path: Optional[str] = Field(
        default=None,
        validation_alias="WW_SHARD_EXPERIENCE_PATH",
    )
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    def get_effective_api_key(self) -> Optional[str]:
        """Return the most specific API key available."""
        return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or self.openrouter_api_key or self.llm_api_key or self.openai_api_key

    def is_runtime_ready(self) -> bool:
        """Check if both an API key and a model are configured."""
        return bool(self.get_effective_api_key() and self.llm_model)

    # Auth
    jwt_secret: str = Field(default="CHANGE_ME_IN_PRODUCTION", validation_alias="WW_JWT_SECRET")
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, validation_alias="WW_JWT_EXPIRE_MINUTES")
    data_encryption_key: Optional[str] = Field(default=None, validation_alias="WW_DATA_ENCRYPTION_KEY")
    resend_api_key: Optional[str] = Field(default=None, validation_alias="RESEND_API_KEY")
    resend_from_email: str = Field(
        default="noreply@worldweaver.example.com",
        validation_alias="RESEND_FROM_EMAIL",
    )
# Global settings instance
settings = Settings()
