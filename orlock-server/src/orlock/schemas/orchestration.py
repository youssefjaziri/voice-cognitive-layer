from pydantic import BaseModel, Field
from typing import Dict, Optional
from .metadata import SpeechMetadata
from .intent import IntentCategory


class OrchestrationResponse(BaseModel):
    """Response from the intelligent orchestration pipeline."""
    user_text: str = Field(..., description="The user's input (transcribed or text)")
    llm_response: str = Field(..., description="Generated response from LLM")

    intent: IntentCategory
    intent_confidence: float = Field(..., ge=0.0, le=1.0)

    speech_quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall speech quality (if from audio)")
    speech_quality_level: Optional[str] = None

    metadata: Optional[SpeechMetadata] = None

    routed_model: Optional[str] = Field(None, description="Ollama model selected by the model router")

    rag_used: bool = Field(False, description="Whether RAG retrieved relevant context for this query")
    rag_context: Optional[str] = Field(None, description="The knowledge base excerpts injected into the prompt")

    navigation_goal: Optional[str] = Field(None, description="Nav stack location ID to send to /set_goal, if navigation intent")

    processing_time_ms: float = Field(..., description="Total time for orchestration pipeline")
    pipeline_stages: Dict[str, float] = Field(
        default={},
        description="Processing time for each stage in ms"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_text": "What is voice activity detection?",
                "llm_response": "Voice Activity Detection (VAD) is a technique...",
                "intent": "technical",
                "intent_confidence": 0.89,
                "speech_quality_score": 0.87,
                "speech_quality_level": "good",
                "processing_time_ms": 1250,
                "pipeline_stages": {
                    "intent_detection": 150,
                    "context_retrieval": 50,
                    "quality_analysis": 75,
                    "prompt_building": 100,
                    "llm_generation": 850,
                    "response_validation": 25
                }
            }
        }
