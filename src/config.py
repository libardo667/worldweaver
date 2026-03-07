import os
from typing import Any, Dict, Optional

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
    llm_model: str = "aion-labs/aion-2.0"
    embedding_model: str = "openai/text-embedding-3-small"
    
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2500
    llm_timeout_seconds: int = 30
    llm_retries: int = 2
    llm_frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    llm_presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    llm_referee_model: Optional[str] = Field(
        default=None,
        validation_alias="LLM_REFEREE_MODEL",
    )
    llm_referee_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        validation_alias="LLM_REFEREE_TEMPERATURE",
    )
    llm_referee_frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        validation_alias="LLM_REFEREE_FREQUENCY_PENALTY",
    )
    llm_referee_presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        validation_alias="LLM_REFEREE_PRESENCE_PENALTY",
    )
    llm_narrator_model: Optional[str] = Field(
        default=None,
        validation_alias="LLM_NARRATOR_MODEL",
    )
    llm_narrator_temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        validation_alias="LLM_NARRATOR_TEMPERATURE",
    )
    llm_narrator_frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        validation_alias="LLM_NARRATOR_FREQUENCY_PENALTY",
    )
    llm_narrator_presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        validation_alias="LLM_NARRATOR_PRESENCE_PENALTY",
    )
    
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
    session_consistency_mode: str = Field(
        default="cache",
        validation_alias="WW_SESSION_CONSISTENCY_MODE",
    )
    
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
    enable_simulation_tick: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_SIMULATION_TICK",
    )
    enable_story_smoothing: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_STORY_SMOOTHING",
    )
    enable_story_deepening: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_STORY_DEEPENING",
    )
    enable_staged_action_pipeline: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_STAGED_ACTION_PIPELINE",
    )
    enable_strict_action_validation: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_STRICT_ACTION_VALIDATION",
    )
    enable_strict_three_layer_architecture: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_STRICT_THREE_LAYER_ARCHITECTURE",
    )
    enable_frontier_prefetch: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_FRONTIER_PREFETCH",
    )
    enable_assistive_spatial: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_ASSISTIVE_SPATIAL",
    )
    enable_spatial_auto_fixes: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_SPATIAL_AUTO_FIXES",
    )
    enable_jit_beat_generation: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_JIT_BEAT_GENERATION",
    )
    enable_turn_endpoint: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_TURN_ENDPOINT",
    )
    prefetch_max_per_session: int = Field(default=6, ge=0, le=50)
    prefetch_ttl_seconds: int = Field(default=180, ge=5, le=3600)
    prefetch_idle_trigger_seconds: int = Field(default=8, ge=1, le=300)
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
    motif_ledger_max_items: int = Field(
        default=32,
        ge=8,
        le=200,
        validation_alias="WW_MOTIF_LEDGER_MAX_ITEMS",
    )
    motif_extract_max_per_turn: int = Field(
        default=8,
        ge=1,
        le=50,
        validation_alias="WW_MOTIF_EXTRACT_MAX_PER_TURN",
    )
    motif_palette_min_anchors: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias="WW_MOTIF_PALETTE_MIN_ANCHORS",
    )
    enable_motif_referee_audit: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_MOTIF_REFEREE_AUDIT",
    )
    motif_referee_revise_budget: int = Field(
        default=1,
        ge=0,
        le=1,
        validation_alias="WW_MOTIF_REFEREE_REVISE_BUDGET",
    )
    enable_world_graph_extraction: bool = True
    enable_world_projection: bool = True
    enable_v3_projection_expansion: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_V3_PROJECTION_EXPANSION",
    )
    enable_v3_player_hint_channel: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_V3_PLAYER_HINT_CHANNEL",
    )
    enable_v3_projection_seeded_narration: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_V3_PROJECTION_SEEDED_NARRATION",
    )
    enable_projection_referee_scoring: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_PROJECTION_REFEREE_SCORING",
    )
    v3_projection_max_depth: int = Field(
        default=2,
        ge=0,
        le=8,
        validation_alias="WW_V3_PROJECTION_MAX_DEPTH",
    )
    v3_projection_max_nodes: int = Field(
        default=12,
        ge=0,
        le=250,
        validation_alias="WW_V3_PROJECTION_MAX_NODES",
    )
    v3_projection_time_budget_ms: int = Field(
        default=120,
        ge=0,
        le=10000,
        validation_alias="WW_V3_PROJECTION_TIME_BUDGET_MS",
    )
    v3_projection_ttl_seconds: int = Field(
        default=180,
        ge=5,
        le=86400,
        validation_alias="WW_V3_PROJECTION_TTL_SECONDS",
    )
    enable_legacy_test_seeds: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_LEGACY_TEST_SEEDS",
    )
    enable_dev_reset: bool = Field(
        default=True,
        validation_alias="WW_ENABLE_DEV_RESET",
    )
    enable_adaptive_projection_pruning: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_ADAPTIVE_PROJECTION_PRUNING",
    )
    enable_projection_pressure_tiers: bool = Field(
        default=False,
        validation_alias="WW_ENABLE_PROJECTION_PRESSURE_TIERS",
    )
    projection_pressure_prune_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        validation_alias="WW_PROJECTION_PRESSURE_PRUNE_THRESHOLD",
    )
    projection_pressure_stubs_only_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        validation_alias="WW_PROJECTION_PRESSURE_STUBS_ONLY_THRESHOLD",
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


    def is_runtime_ready(self) -> bool:
        """Check if both an API key and a model are configured."""
        return bool(self.get_effective_api_key() and self.llm_model)

    def get_v3_runtime_settings(self) -> Dict[str, Any]:
        """Return v3 runtime controls in one reproducible diagnostics payload."""
        ttl_seconds = max(
            1,
            min(
                int(self.v3_projection_ttl_seconds),
                int(self.prefetch_ttl_seconds),
            ),
        )
        return {
            "flags": {
                "frontier_prefetch_enabled": bool(self.enable_frontier_prefetch),
                "projection_expansion_enabled": bool(
                    self.enable_frontier_prefetch and self.enable_v3_projection_expansion
                ),
                "player_hint_channel_enabled": bool(self.enable_v3_player_hint_channel),
                "projection_seeded_narration_enabled": bool(
                    self.enable_v3_projection_seeded_narration
                ),
                "projection_referee_scoring_enabled": bool(
                    self.enable_projection_referee_scoring
                ),
                "adaptive_pruning_enabled": bool(self.enable_adaptive_projection_pruning),
                "pressure_tiers_enabled": bool(self.enable_projection_pressure_tiers),
            },
            "budgets": {
                "max_projection_depth": max(0, int(self.v3_projection_max_depth)),
                "max_projection_nodes": max(0, int(self.v3_projection_max_nodes)),
                "projection_time_budget_ms": max(0, int(self.v3_projection_time_budget_ms)),
                "projection_ttl_seconds": ttl_seconds,
                "prefetch_ttl_seconds": max(1, int(self.prefetch_ttl_seconds)),
                "projection_pressure_prune_threshold": float(
                    self.projection_pressure_prune_threshold
                ),
                "projection_pressure_stubs_only_threshold": float(
                    self.projection_pressure_stubs_only_threshold
                ),
            },
        }


# Global settings instance
settings = Settings()
