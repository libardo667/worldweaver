"""Model registry with pricing data and session cost estimation.

Provides metadata for OpenRouter models used by WorldWeaver, including
per-token pricing, creative quality ratings, and estimated session costs.
"""

from typing import Any, Dict, Optional

# Tokens per turn estimated from actual WorldWeaver LLM call patterns:
#   - storylet adaptation: ~1500 input, ~700 output
#   - runtime synthesis:   ~1200 input, ~800 output
#   - command interpretation: ~1800 input, ~600 output
# Average across call types: ~1500 input, ~700 output per call.
# Estimated 1.5 LLM calls per player turn.
_DEFAULT_INPUT_TOKENS_PER_TURN = 2250
_DEFAULT_OUTPUT_TOKENS_PER_TURN = 1050

# World generation is a one-time cost: ~3000 input, ~5000 output.
_WORLD_GEN_INPUT_TOKENS = 3000
_WORLD_GEN_OUTPUT_TOKENS = 5000


MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "arcee-ai/trinity-large-preview:free": {
        "label": "Arcee Trinity (Free)",
        "tier": "free",
        "input_per_m": 0.00,
        "output_per_m": 0.00,
        "context_window": 131_000,
        "creative_quality": 3,
        "notes": "Strong roleplay/creative writing focus. Free tier with rate limits.",
    },
    "deepseek/deepseek-chat:free": {
        "label": "DeepSeek Chat (Free)",
        "tier": "free",
        "input_per_m": 0.00,
        "output_per_m": 0.00,
        "context_window": 64_000,
        "creative_quality": 2,
        "notes": "Decent general chat. Free tier with rate limits.",
    },
    "qwen/qwen3.5-flash-02-23": {
        "label": "Qwen 3.5 Flash",
        "tier": "ultra-low",
        "input_per_m": 0.10,
        "output_per_m": 0.40,
        "context_window": 1_000_000,
        "creative_quality": 2,
        "notes": "Fast and ultra-cheap. Acceptable prose, huge context window.",
    },
    "openai/gpt-4o-mini": {
        "label": "GPT-4o Mini",
        "tier": "budget",
        "input_per_m": 0.15,
        "output_per_m": 0.60,
        "context_window": 128_000,
        "creative_quality": 3,
        "notes": "Surprisingly good creative output for the price.",
    },
    "deepseek/deepseek-r1": {
        "label": "DeepSeek R1",
        "tier": "budget",
        "input_per_m": 0.70,
        "output_per_m": 2.50,
        "context_window": 64_000,
        "creative_quality": 2,
        "notes": "Strong reasoning model with internal chain-of-thought. Adds latency overhead for creative prose; better suited for structured/analytical tasks.",
    },
    "google/gemini-3-flash-preview": {
        "label": "Gemini 3 Flash",
        "tier": "budget",
        "input_per_m": 0.50,
        "output_per_m": 3.00,
        "context_window": 1_050_000,
        "creative_quality": 3,
        "notes": "Good all-rounder with a massive context window.",
    },
    "openai/gpt-4o": {
        "label": "GPT-4o",
        "tier": "standard",
        "input_per_m": 2.50,
        "output_per_m": 10.00,
        "context_window": 128_000,
        "creative_quality": 4,
        "notes": "Strong creative output and brainstorming. Solid all-rounder.",
    },
    "anthropic/claude-sonnet-4": {
        "label": "Claude Sonnet 4",
        "tier": "standard",
        "input_per_m": 3.00,
        "output_per_m": 15.00,
        "context_window": 1_000_000,
        "creative_quality": 5,
        "notes": "Best prose quality. Natural dialogue, consistent voice, rich descriptions.",
    },
    "anthropic/claude-opus-4": {
        "label": "Claude Opus 4",
        "tier": "premium",
        "input_per_m": 15.00,
        "output_per_m": 75.00,
        "context_window": 200_000,
        "creative_quality": 5,
        "notes": "Premium quality with deepest context understanding. Expensive.",
    },
}


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Return registry entry for *model_id*, or ``None`` if not found."""
    return MODEL_REGISTRY.get(model_id)


def estimate_session_cost(
    model_id: str,
    turns: int = 10,
    *,
    include_world_gen: bool = False,
) -> Dict[str, Any]:
    """Estimate cost for a game session.

    Returns a dict with ``input_tokens``, ``output_tokens``,
    ``input_cost``, ``output_cost``, ``total_cost``, and ``tier``.
    If the model is not in the registry, costs are estimated at $0.
    """
    info = MODEL_REGISTRY.get(model_id, {})
    input_per_m = float(info.get("input_per_m", 0))
    output_per_m = float(info.get("output_per_m", 0))

    input_tokens = turns * _DEFAULT_INPUT_TOKENS_PER_TURN
    output_tokens = turns * _DEFAULT_OUTPUT_TOKENS_PER_TURN

    if include_world_gen:
        input_tokens += _WORLD_GEN_INPUT_TOKENS
        output_tokens += _WORLD_GEN_OUTPUT_TOKENS

    input_cost = (input_tokens / 1_000_000) * input_per_m
    output_cost = (output_tokens / 1_000_000) * output_per_m

    return {
        "model": model_id,
        "label": info.get("label", model_id),
        "tier": info.get("tier", "unknown"),
        "creative_quality": info.get("creative_quality", 0),
        "turns": turns,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(input_cost + output_cost, 4),
        "notes": info.get("notes", ""),
    }


def list_available_models() -> list[Dict[str, Any]]:
    """Return all registered models with 10-turn cost estimates."""
    result = []
    for model_id, info in MODEL_REGISTRY.items():
        estimate = estimate_session_cost(model_id, turns=10)
        result.append(
            {
                "model_id": model_id,
                "label": info["label"],
                "tier": info["tier"],
                "creative_quality": info["creative_quality"],
                "context_window": info["context_window"],
                "estimated_10_turn_cost_usd": estimate["total_cost_usd"],
                "notes": info["notes"],
            }
        )
    # Sort by cost (free first, then ascending)
    result.sort(key=lambda m: m["estimated_10_turn_cost_usd"])
    return result
