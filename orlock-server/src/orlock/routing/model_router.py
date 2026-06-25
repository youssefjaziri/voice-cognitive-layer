"""
Model router: selects the appropriate Ollama model based on intent and speech quality.

Routing tiers
─────────────
fast     → lightweight model for simple social interactions (low latency)
default  → general-purpose model for most queries
capable  → larger model for technical/multi-step reasoning
safe     → deterministic output for high-stakes intents (temperature forced to 0)
"""
import logging
import os
from typing import Optional

import requests

from ..schemas.intent import IntentCategory

logger = logging.getLogger(__name__)

# ── routing table ─────────────────────────────────────────────────────────────
_TIERS: dict = {
    "fast": {
        "model": "tinyllama:latest",
        "categories": {
            IntentCategory.GREETING,
            IntentCategory.ACKNOWLEDGEMENT,
            IntentCategory.CONVERSATIONAL,
        },
    },
    "default": {
        "model": "llama3.2:1b",          # 1B — ~2x faster than 3B on CPU, good enough for nav/Q&A
        "categories": {
            IntentCategory.QUESTION,
            IntentCategory.CLARIFICATION,
            IntentCategory.SUMMARIZATION,
            IntentCategory.NAVIGATION,
            IntentCategory.COMMAND,
        },
    },
    "capable": {
        "model": "llama3.2:latest",      # 3.2B — kept for technical/explanation reasoning
        "categories": {
            IntentCategory.TECHNICAL,
            IntentCategory.TASK_EXECUTION,
            IntentCategory.EXPLANATION,
        },
    },
    "safe": {
        "model": "llama3.2:latest",      # deterministic, still fast
        "categories": {IntentCategory.EMERGENCY, IntentCategory.SYSTEM_CONTROL},
        "temperature_override": 0.0,
    },
}

# pre-built intent → tier lookup
_INTENT_TO_TIER: dict[IntentCategory, dict] = {}
for _tier in _TIERS.values():
    for _cat in _tier["categories"]:
        _INTENT_TO_TIER[_cat] = _tier


class ModelRouter:
    """Selects Ollama model and optional temperature override for each request."""

    def __init__(self, available_models: Optional[list] = None):
        if available_models is None:
            available_models = self.get_available_models()
        self._available: set[str] = set(available_models)
        if self._available:
            logger.info(f"ModelRouter: available models = {sorted(self._available)}")
        else:
            logger.warning("ModelRouter: could not reach Ollama, routing to default")

    def select(self, intent, quality) -> tuple[str, Optional[float]]:
        """
        Returns (model_name, temperature_override).
        temperature_override is None if the orchestration service should use its own value.
        """
        tier = _INTENT_TO_TIER.get(intent.category, _TIERS["default"])
        model: str = tier["model"]
        temp_override: Optional[float] = tier.get("temperature_override")

        # Only truly unintelligible audio forces the safe model.
        # "poor" quality still routes normally — intent confidence is the
        # better signal for how certain we are about the request.
        if quality.quality_level == "unintelligible":
            model = _TIERS["safe"]["model"]
            temp_override = 0.05
            logger.debug(f"ModelRouter: unintelligible audio → safe model ({model})")

        # Low-confidence intent → don't use fast tier (might misclassify)
        if intent.confidence < 0.4 and tier is _TIERS.get("fast"):
            model = _TIERS["default"]["model"]
            logger.debug("ModelRouter: low confidence intent → default model")

        # Availability guard: fall back to default if chosen model isn't installed
        if self._available and model not in self._available:
            fallback = _TIERS["default"]["model"]
            logger.warning(f"ModelRouter: {model} not available, falling back to {fallback}")
            model = fallback

        logger.debug(
            f"ModelRouter: intent={intent.category.value} quality={quality.quality_level}"
            f" → model={model} temp_override={temp_override}"
        )
        return model, temp_override

    @staticmethod
    def get_available_models() -> list[str]:
        """Query Ollama for installed model names."""
        try:
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            r = requests.get(f"{base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception as exc:
            logger.warning(f"ModelRouter: could not list Ollama models: {exc}")
            return []
