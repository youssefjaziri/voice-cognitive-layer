"""Intent detection using LLM classification."""
import logging
import json
import asyncio
from typing import Optional, Dict, List
from ..schemas.intent import IntentResult, IntentCategory
from ..schemas.metadata import SpeechMetadata
from ..intent.categories import INTENT_DESCRIPTIONS
from ..services.llm_service import LLMService


logger = logging.getLogger(__name__)


INTENT_CLASSIFIER_PROMPT = """Classify the user's intent. Pick exactly one category.

Categories: {categories}

User: "{user_input}"

Reply with ONLY valid JSON:
{{"intent": "<category>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>", "related_intents": []}}"""


# Keyword patterns for syntactically unambiguous short intents.
# Only categories where the surface form alone is decisive are listed here.
# All other categories go to the LLM classifier.
_RULE_PATTERNS: Dict[str, List[str]] = {
    "greeting": [
        "hello", "hi ", "hi,", "hi!", "hi.", "hey ", "hey,", "hey!",
        "good morning", "good evening", "good afternoon", "good day",
        "greetings", "howdy", "salut", "bonjour",
    ],
    "acknowledgement": [
        "got it", "okay", "ok,", "ok.", "ok!", "understood", "alright",
        "thank you", "thanks", "perfect", "noted", "will do",
        "sounds good", "sure,", "sure.", "yes, i understand",
        "i understand", "great, thanks",
    ],
}
# Maximum text length for the rule-based check — longer utterances are unlikely
# to be pure greetings or acknowledgements even if they contain a matching prefix.
_RULE_MAX_CHARS = 40


class IntentDetector:
    """Detects user intent from text input."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        self._intent_cache: Dict[str, IntentResult] = {}
        self._cache_max_size = 1000

    async def detect(self, text: str, metadata: Optional[SpeechMetadata] = None) -> IntentResult:
        """Detect intent from text input."""
        # Check cache first
        cached = self._get_cached_intent(text)
        if cached:
            logger.debug(f"Intent from cache for: {text[:50]}")
            return cached

        # Rule-based pre-classifier for syntactically unambiguous short intents.
        # Eliminates the ~3.8 s Llama 3.2 call for greetings and acknowledgements,
        # reducing their end-to-end latency from ~5.3 s to ~1.5 s (generation only).
        rule_result = self._rule_based_classify(text)
        if rule_result:
            logger.debug(f"Intent from rules ({rule_result.category.value}) for: {text[:50]}")
            self._cache_intent(text, rule_result)
            return rule_result

        try:
            intent_result = await self._classify_with_llm(text)
            self._cache_intent(text, intent_result)
            return intent_result
        except Exception as e:
            logger.error(f"Intent detection failed: {e}. Falling back to CONVERSATIONAL")
            return IntentResult(
                category=IntentCategory.CONVERSATIONAL,
                confidence=0.5,
                reasoning="Intent detection failed, defaulting to conversational",
                related_categories=[],
                suggested_response_style="neutral, helpful"
            )

    def _rule_based_classify(self, text: str) -> Optional[IntentResult]:
        """Keyword pre-classifier for greetings and acknowledgements.

        Returns an IntentResult immediately if the text is short and starts with
        an unambiguous pattern. Returns None for all other inputs so the LLM
        classifier handles them as normal.
        """
        if len(text) > _RULE_MAX_CHARS:
            return None

        lowered = text.strip().lower()

        for intent_name, patterns in _RULE_PATTERNS.items():
            for pattern in patterns:
                if lowered == pattern.strip() or lowered.startswith(pattern):
                    category = IntentCategory(intent_name)
                    return IntentResult(
                        category=category,
                        confidence=0.95,
                        reasoning=f"Rule-based: matched pattern '{pattern.strip()}'",
                        related_categories=[],
                        suggested_response_style=self._get_suggested_style(category, 0.95),
                    )

        return None

    async def _classify_with_llm(self, text: str) -> IntentResult:
        """Use LLM to classify intent."""
        # Compact one-line list — fewer tokens means faster generation
        categories_text = ", ".join(cat.value for cat in IntentCategory)

        prompt = INTENT_CLASSIFIER_PROMPT.format(
            categories=categories_text,
            user_input=text
        )

        system_prompt = "You are a precise intent classification system. Respond only with valid JSON."

        # llama3.2 handles structured JSON reliably; tinyllama produces garbage for
        # 13-category prompts and always falls back to CONVERSATIONAL (tested: 9.7% accuracy).
        response = await asyncio.to_thread(
            self.llm_service.message_to_llm_text,
            prompt,
            system_prompt,
            0.1,
            "llama3.2:latest",
        )

        return self._parse_intent_response(response)

    def _parse_intent_response(self, response: str) -> IntentResult:
        """Parse LLM response to IntentResult."""
        try:
            # Extract first JSON object even if the model prepended explanation text
            raw = response.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)

            intent_cat = IntentCategory(data.get("intent", "conversational"))
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            related = []
            for cat_name, score in data.get("related_intents", []):
                try:
                    related.append((IntentCategory(cat_name), float(score)))
                except (ValueError, KeyError):
                    pass

            style = self._get_suggested_style(intent_cat, confidence)

            return IntentResult(
                category=intent_cat,
                confidence=min(1.0, max(0.0, confidence)),
                reasoning=reasoning,
                related_categories=related,
                suggested_response_style=style
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse intent response: {e}. Response: {response}")
            return IntentResult(
                category=IntentCategory.CONVERSATIONAL,
                confidence=0.3,
                reasoning="Failed to parse intent, defaulting to conversational",
                related_categories=[],
                suggested_response_style="neutral"
            )

    def _get_suggested_style(self, intent: IntentCategory, confidence: float) -> str:
        """Get suggested response style for intent."""
        style_map = {
            IntentCategory.TECHNICAL: "professional, code-focused, structured",
            IntentCategory.COMMAND: "action-oriented, concise, directive",
            IntentCategory.QUESTION: "informative, clear, direct",
            IntentCategory.EXPLANATION: "detailed, educational, step-by-step",
            IntentCategory.GREETING: "warm, friendly, personable",
            IntentCategory.EMERGENCY: "urgent, focused, solution-oriented",
            IntentCategory.ACKNOWLEDGEMENT: "brief, affirmative, supportive",
            IntentCategory.CLARIFICATION: "explicit, thorough, unambiguous",
            IntentCategory.CONVERSATIONAL: "natural, conversational, engaging",
            IntentCategory.SUMMARIZATION: "concise, bullet-point, organized",
            IntentCategory.TASK_EXECUTION: "structured, methodical, comprehensive",
            IntentCategory.SYSTEM_CONTROL: "precise, technical, procedural",
            IntentCategory.NAVIGATION: "clear, sequential, oriented",
        }

        base_style = style_map.get(intent, "neutral, helpful")

        if confidence < 0.6:
            base_style += ", ask for clarification if needed"

        return base_style

    def _get_cached_intent(self, text: str) -> Optional[IntentResult]:
        """Get cached intent if available."""
        key = self._make_cache_key(text)
        return self._intent_cache.get(key)

    def _cache_intent(self, text: str, result: IntentResult):
        """Cache intent result."""
        if len(self._intent_cache) >= self._cache_max_size:
            # Clear cache if too large (simple FIFO)
            first_key = next(iter(self._intent_cache))
            del self._intent_cache[first_key]

        key = self._make_cache_key(text)
        self._intent_cache[key] = result

    @staticmethod
    def _make_cache_key(text: str) -> str:
        """Create cache key from text (normalized)."""
        return text.strip().lower()[:200]
