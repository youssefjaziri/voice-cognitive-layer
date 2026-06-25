"""Orchestrated audio endpoint - intelligent transcription and response generation."""
import logging
import io
from pathlib import Path
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from ....schemas.metadata import SpeechMetadata
from ....schemas.orchestration import OrchestrationResponse
from ....services.orchestration_service import OrchestrationService

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperModel = None


logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
orchestration_service = OrchestrationService()
_whisper_model = None

def get_whisper_model():
    """Lazy load Whisper model on first use."""
    global _whisper_model
    if _whisper_model is None and WHISPER_AVAILABLE:
        logger.info("Loading Whisper model for orchestrated endpoint...")
        _whisper_model = WhisperModel("base", device="cpu")
        logger.info("Whisper model loaded successfully")
    return _whisper_model

def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """Transcribe audio from bytes using Whisper."""
    if not WHISPER_AVAILABLE:
        logger.warning("Whisper not available")
        return "[TRANSCRIPTION_UNAVAILABLE] Whisper not available"

    try:
        model = get_whisper_model()
        if model is None:
            return "[TRANSCRIPTION_ERROR] Whisper model failed to load"

        # Write bytes to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            logger.info(f"Transcribing audio ({len(audio_bytes)} bytes)")
            segments, info = model.transcribe(tmp_path, language="en")
            transcript = " ".join([segment.text.strip() for segment in segments])

            if not transcript.strip():
                transcript = "[TRANSCRIPTION_EMPTY] No speech detected"
                logger.warning("No speech detected in audio")

            logger.info(f"Transcription complete: {transcript[:100]}...")
            return transcript

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        error_msg = f"[TRANSCRIPTION_ERROR] {str(e)}"
        logger.error(f"Transcription failed: {str(e)}")
        return error_msg


@router.post("/orchestrated/audio", response_model=OrchestrationResponse)
async def orchestrated_audio(
    user_id: str = Form(...),
    audio: UploadFile = File(...),
    metadata_json: str = Form(None),
    system_prompt: str = Form(None)
):
    """
    Orchestrated audio endpoint with intelligent intent detection and response generation.

    Accepts:
    - user_id: User identifier
    - audio: Audio file (WAV)
    - metadata_json: JSON-encoded SpeechMetadata with VAD and audio quality metrics
    - system_prompt: Optional custom system prompt

    Returns:
    - OrchestrationResponse with intent, quality score, and response
    """

    try:
        # Validate and parse metadata
        try:
            metadata = SpeechMetadata.model_validate_json(metadata_json)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {e}")

        # Validate audio file
        if not audio.filename:
            raise HTTPException(status_code=400, detail="Audio file is required")

        audio_content = await audio.read()
        if not audio_content:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        # Transcribe audio
        logger.debug(f"Transcribing audio for user {user_id}")
        transcript = transcribe_audio_bytes(audio_content)

        if not transcript:
            raise HTTPException(status_code=500, detail="Transcription failed")

        logger.debug(f"Transcribed: {transcript[:50]}")

        # Process through orchestration pipeline
        logger.debug("Starting orchestration pipeline")
        result = await orchestration_service.process_transcription(
            user_id=user_id,
            transcription=transcript,
            metadata=metadata,
            user_system_prompt=system_prompt
        )

        logger.info(
            f"Orchestrated response for {user_id}: "
            f"intent={result.intent.value}, "
            f"quality={result.speech_quality_level}, "
            f"time={result.processing_time_ms:.0f}ms"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in orchestrated audio endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
