import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = (
    None
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("PYTEST_VERSION")
    else ".env"
)


class Settings(BaseSettings):
    """System-wide configuration settings."""
    
    # LLM Settings
    llm_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-r1"
    embedding_model: str = "openai/text-embedding-3-small"
    
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2500
    llm_timeout_seconds: int = 15
    llm_retries: int = 2
    
    # Game Logic Settings
    min_eligible_storylets: int = 3
    auto_generate_count: int = 5
    
    # Spatial Settings
    spatial_max_radius: int = 20
    location_search_radius: int = 20
    
    # Cache & Performance
    cache_ttl_seconds: int = 30
    state_manager_cache_max_size: int = 500
    state_manager_cache_ttl_seconds: int = 3600
    navigator_cache_max_size: int = 32
    navigator_cache_ttl_seconds: int = 3600
    
    # Narrative Settings
    bridge_limit: int = 3
    coherence_threshold: float = 0.6
    llm_semantic_floor_probability: float = Field(default=0.05, ge=0.0, le=1.0)
    llm_recency_penalty: float = Field(default=0.3, ge=0.0, le=1.0)
    enable_constellation: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_CONSTELLATION",
    )
    enable_runtime_adaptation: bool = True
    enable_runtime_storylet_synthesis: bool = True
    runtime_synthesis_max_candidates: int = Field(default=2, ge=1, le=3)
    runtime_synthesis_min_eligible_storylets: int = Field(default=1, ge=0, le=20)
    runtime_synthesis_min_top_score: float = Field(default=0.22, ge=0.0, le=1.0)
    runtime_synthesis_repetition_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0
    )
    runtime_synthesis_recent_window: int = Field(default=6, ge=1, le=50)
    runtime_synthesis_max_per_session: int = Field(default=3, ge=0, le=20)
    runtime_synthesis_rate_window_seconds: int = Field(
        default=3600, ge=60, le=86400
    )
    runtime_synthesis_ttl_minutes: int = Field(default=90, ge=5, le=1440)
    enable_world_graph_extraction: bool = True
    enable_world_projection: bool = True
    enable_legacy_test_seeds: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_LEGACY_TEST_SEEDS",
    )
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_effective_api_key(self) -> Optional[str]:
        """Return the most specific API key available."""
        return (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or self.openrouter_api_key
            or self.llm_api_key
            or self.openai_api_key
        )


# Global settings instance
settings = Settings()
