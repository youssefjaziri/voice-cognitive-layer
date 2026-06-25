"""
speech_segmentation_node.py
-----------------------------
Subscribes to /speech_detected and /audio/raw, implements a state machine
to detect speech segments, buffers audio, and saves chunks as .wav files.
Includes pre-buffering for sentence start capture, amplitude filtering for
near-field audio detection, and sends audio to Orlock API for transcription.

Topics subscribed:
    /speech_detected    (std_msgs/msg/Bool)      – VAD output
    /audio/raw          (std_msgs/msg/Int16MultiArray) – PCM audio

Dependencies (install in your ROS2 environment):
    pip install soundfile numpy
"""

from collections import deque
from enum import Enum
import time
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int16MultiArray, String

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from vad_component.orlock_api_client import OrlockAPIClient

# Import monitoring with better error handling
try:
    # Try absolute path first
    sys.path.insert(0, '/home/youssef/PFE2/monitoring')
    from pipeline_logger import get_logger, PipelineStage
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    get_logger = None
    PipelineStage = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16_000          # Hz – must match mic_node
SILENCE_THRESHOLD = 0.5       # seconds – how long to wait for silence
MIN_SEGMENT_DURATION = 0.3    # seconds – ignore very short segments
INT16_MAX = 32768.0           # used to normalise int16 ↔ float32


class VadState(Enum):
    """State machine states for speech detection."""
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    STOPPING = "STOPPING"


class SpeechSegmentationNode(Node):
    """
    Buffers audio frames during detected speech and saves segments to .wav files.
    Includes pre-buffering to capture sentence starts and amplitude filtering for
    near-field audio. Sends audio chunks to Orlock API for server-side transcription.

    Parameters (ROS2 params):
        output_dir (str): Directory to save audio chunks. Default: "./audio_chunks"
        silence_threshold (double): Silence duration before stopping recording (sec).
                                    Default: 0.5
        min_duration (double): Minimum segment duration to save (seconds).
                              Default: 0.3
        pre_buffer_duration (double): Duration of pre-buffer to capture sentence starts (sec).
                                      Default: 1.0
        amplitude_threshold (double): RMS energy threshold for near-field detection.
                                      Default: 0.02
        enable_amplitude_filter (bool): Enable amplitude-based filtering to exclude far-field audio.
                                        Default: True
        verbose (bool): If True, log all state transitions and frame stats.
                        Default: False
        enable_api (bool): Enable sending audio to Orlock API. Default: False
        api_url (str): Orlock API URL. Default: "http://localhost:8000"
        api_user_id (str): User ID for API requests. Default: "default_user"
        api_system_prompt (str): Optional system prompt for LLM. Default: None
    """

    def __init__(self) -> None:
        super().__init__('speech_segmentation_node')

        # Initialize monitoring logger if available
        self.monitor_logger = None
        if MONITORING_AVAILABLE:
            self.monitor_logger = get_logger()
            self.monitor_logger.info("SYSTEM", "Speech Segmentation Node starting...")

        # --- declare & read parameters ----------------------------------------
        self.declare_parameter('output_dir', './audio_chunks')
        self.declare_parameter('silence_threshold', SILENCE_THRESHOLD)
        self.declare_parameter('min_duration', MIN_SEGMENT_DURATION)
        self.declare_parameter('verbose', False)
        self.declare_parameter('pre_buffer_duration', 1.0)
        self.declare_parameter('amplitude_threshold', 0.02)
        self.declare_parameter('enable_amplitude_filter', True)
        # --- API parameters ----
        self.declare_parameter('enable_api', False)
        self.declare_parameter('api_url', 'http://localhost:8000')
        self.declare_parameter('api_user_id', 'default_user')
        self.declare_parameter('api_system_prompt', '', descriptor=None)

        self._output_dir: str = (
            self.get_parameter('output_dir').get_parameter_value().string_value
        )
        self._silence_threshold: float = (
            self.get_parameter('silence_threshold').get_parameter_value().double_value
        )
        self._min_duration: float = (
            self.get_parameter('min_duration').get_parameter_value().double_value
        )
        self._verbose: bool = (
            self.get_parameter('verbose').get_parameter_value().bool_value
        )
        self._pre_buffer_duration: float = (
            self.get_parameter('pre_buffer_duration').get_parameter_value().double_value
        )
        self._amplitude_threshold: float = (
            self.get_parameter('amplitude_threshold').get_parameter_value().double_value
        )
        self._enable_amplitude_filter: bool = (
            self.get_parameter('enable_amplitude_filter').get_parameter_value().bool_value
        )
        # --- API parameters ----
        self._enable_api: bool = (
            self.get_parameter('enable_api').get_parameter_value().bool_value
        )
        self._api_url: str = (
            self.get_parameter('api_url').get_parameter_value().string_value
        )
        self._api_user_id: str = (
            self.get_parameter('api_user_id').get_parameter_value().string_value
        )
        api_system_value = self.get_parameter('api_system_prompt').get_parameter_value().string_value
        self._api_system_prompt: Optional[str] = (
            api_system_value if api_system_value.strip() else None
        )

        # Initialize API client if enabled
        self._api_client = None
        if self._enable_api:
            # Use orchestrated endpoint by default for intelligent response generation
            self._api_client = OrlockAPIClient(self._api_url, use_orchestrated=True)
            self.get_logger().info(f'[API] Enabled (Orchestrated) - {self._api_url}')
            if self.monitor_logger:
                self.monitor_logger.info("API", f"Enabled (Orchestrated) - {self._api_url}")

        # Create output directory if it doesn't exist
        output_path = Path(self._output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self._output_dir = str(output_path.resolve())

        # --- state machine  ---------------------------------------------------
        self._state: VadState = VadState.IDLE
        self._audio_buffer: list[np.ndarray] = []
        self._chunk_counter: int = 0
        self._silence_start_time: Optional[float] = None
        self._recording_start_time: Optional[float] = None
        self._segment_start_time: Optional[float] = None
        self._tts_playing: bool = False   # True while TTS is speaking

        # --- pre-buffering for capturing sentence starts ----------------------
        self._pre_buffer_max_frames: int = max(1, int(self._pre_buffer_duration * SAMPLE_RATE / 512))
        self._pre_buffer: deque[np.ndarray] = deque(maxlen=self._pre_buffer_max_frames)

        # --- subscribers & publishers -----------------------------------------
        self._sub_speech = self.create_subscription(
            Bool,
            '/speech_detected',
            self._speech_detected_callback,
            10,
        )
        self._sub_audio = self.create_subscription(
            Int16MultiArray,
            '/audio/raw',
            self._audio_callback,
            10,
        )
        # Mute input while TTS is playing to prevent echo feedback.
        # tts_node already publishes this topic — we just need to listen.
        self._sub_tts = self.create_subscription(
            Bool,
            '/tts/speaking',
            self._tts_speaking_callback,
            10,
        )
        self._response_pub = self.create_publisher(String, '/orlock/response', 10)

        self.get_logger().info(
            f'SpeechSegmentationNode ready\n'
            f'  output_dir={self._output_dir}\n'
            f'  silence_threshold={self._silence_threshold}s\n'
            f'  min_duration={self._min_duration}s\n'
            f'  pre_buffer_duration={self._pre_buffer_duration}s ({self._pre_buffer_max_frames} frames)\n'
            f'  amplitude_threshold={self._amplitude_threshold} (RMS)\n'
            f'  enable_amplitude_filter={self._enable_amplitude_filter}\n'
            f'  enable_api={self._enable_api}\n'
            f'  api_url={self._api_url if self._enable_api else "N/A"}\n'
            f'  verbose={self._verbose}'
        )

    # ------------------------------------------------------------------
    def _tts_speaking_callback(self, msg: Bool) -> None:
        """Mute input while TTS is speaking to prevent echo feedback."""
        self._tts_playing = msg.data
        if self._tts_playing and self._state != VadState.IDLE:
            # TTS started while we were mid-recording — abort and discard
            self._state = VadState.IDLE
            self._audio_buffer.clear()
            self._pre_buffer.clear()
            self._silence_start_time = None
            self.get_logger().info('[SEGMENTATION] TTS started — discarding in-progress recording')

    # ------------------------------------------------------------------
    def _speech_detected_callback(self, msg: Bool) -> None:
        """Handle speech detection state changes."""
        if self._tts_playing:
            return  # Ignore all VAD events while GUIDA is speaking

        speech_detected = msg.data

        if speech_detected and self._state == VadState.IDLE:
            # --- IDLE → RECORDING: Start recording ----
            self._state = VadState.RECORDING
            self._audio_buffer.clear()

            # --- Prepend pre-buffered frames to capture sentence start ----
            pre_buffered_frames = self._drain_pre_buffer()
            self._audio_buffer.extend(pre_buffered_frames)

            self._recording_start_time = time.time()
            self._segment_start_time = time.time()
            self._silence_start_time = None

            pre_buffer_duration = len(pre_buffered_frames) * 512 / SAMPLE_RATE
            msg_text = f'Speech started (pre-buffered: {pre_buffer_duration:.2f}s)'
            self.get_logger().info(f'[SEGMENTATION] {msg_text}')
            if self.monitor_logger:
                self.monitor_logger.stage_start("RECORDING")
                self.monitor_logger.info("SEGMENT", msg_text)

        elif not speech_detected and self._state == VadState.RECORDING:
            # --- RECORDING → STOPPING: Silence detected, start timer ----
            self._state = VadState.STOPPING
            self._silence_start_time = time.time()

            if self._verbose:
                self.get_logger().debug('[SEGMENTATION] Silence detected, waiting for threshold...')
                if self.monitor_logger:
                    self.monitor_logger.debug("SEGMENT", "Silence detected, waiting...")

        elif speech_detected and self._state == VadState.STOPPING:
            # --- STOPPING → RECORDING: Speech resumed before silence threshold ----
            self._state = VadState.RECORDING
            self._silence_start_time = None

            if self._verbose:
                self.get_logger().debug('[SEGMENTATION] Speech resumed, continuing recording')
                if self.monitor_logger:
                    self.monitor_logger.debug("SEGMENT", "Speech resumed")

    # ------------------------------------------------------------------
    def _audio_callback(self, msg: Int16MultiArray) -> None:
        """Buffer audio frames during RECORDING state, maintain pre-buffer during IDLE."""
        if not msg.data:
            return

        # Convert int16 PCM to float32 normalized to [-1, 1]
        audio_np = np.array(msg.data, dtype=np.int16).astype(np.float32) / INT16_MAX
        frame_duration = len(audio_np) / SAMPLE_RATE

        # --- IDLE: Maintain pre-buffer for sentence start capture ----
        if self._state == VadState.IDLE:
            self._update_pre_buffer(audio_np)

        # --- RECORDING: Accumulate frames with optional amplitude filtering ----
        elif self._state == VadState.RECORDING:
            # Calculate RMS energy for this frame
            rms_energy = self._get_frame_rms(audio_np)

            # Check amplitude threshold if filtering is enabled
            if self._enable_amplitude_filter and rms_energy < self._amplitude_threshold:
                if self._verbose:
                    self.get_logger().debug(
                        f'[SEGMENTATION] Frame rejected (RMS={rms_energy:.4f} < {self._amplitude_threshold})'
                    )
            else:
                # Frame passes filter or filtering disabled – buffer it
                self._audio_buffer.append(audio_np)
                self._update_pre_buffer(audio_np)  # Maintain for continuity

                if self._verbose:
                    self.get_logger().debug(
                        f'[SEGMENTATION] Buffered frame: {len(audio_np)} samples '
                        f'({frame_duration*1000:.1f}ms), RMS={rms_energy:.4f}, total: {self._get_buffer_duration():.2f}s'
                    )

        # --- STOPPING: Check if silence threshold exceeded ----
        elif self._state == VadState.STOPPING and self._silence_start_time is not None:
            silence_duration = time.time() - self._silence_start_time

            if silence_duration >= self._silence_threshold:
                # Silence threshold reached – save segment and return to IDLE
                self._save_segment()
                self._state = VadState.IDLE
                self._audio_buffer.clear()
                self._pre_buffer.clear()  # Clear pre-buffer on segment end
                self._silence_start_time = None

    # ------------------------------------------------------------------
    def _get_buffer_duration(self) -> float:
        """Calculate total duration of buffered audio in seconds."""
        if not self._audio_buffer:
            return 0.0
        total_samples = sum(len(frame) for frame in self._audio_buffer)
        return total_samples / SAMPLE_RATE

    # ------------------------------------------------------------------
    def _update_pre_buffer(self, audio_frame: np.ndarray) -> None:
        """Add audio frame to circular pre-buffer for sentence start capture."""
        self._pre_buffer.append(audio_frame)

    # ------------------------------------------------------------------
    def _drain_pre_buffer(self) -> list[np.ndarray]:
        """Extract all frames from pre-buffer in order and clear it."""
        frames = list(self._pre_buffer)
        self._pre_buffer.clear()
        return frames

    # ------------------------------------------------------------------
    def _get_frame_rms(self, audio_frame: np.ndarray) -> float:
        """Calculate RMS (root mean square) energy of an audio frame."""
        if len(audio_frame) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio_frame ** 2)))

    # ------------------------------------------------------------------
    def _collect_metadata(self, audio_data: np.ndarray, recording_duration: float) -> dict:
        """Collect audio metadata for orchestration layer."""
        # Calculate RMS energy metrics
        rms_values = []
        frame_size = SAMPLE_RATE // 30  # ~33ms frames

        for i in range(0, len(audio_data), frame_size):
            frame = audio_data[i:i+frame_size]
            if len(frame) > 0:
                rms = float(np.sqrt(np.mean(frame ** 2)))
                rms_values.append(rms)

        rms_energy_min = float(np.min(rms_values)) if rms_values else 0.0
        rms_energy_max = float(np.max(rms_values)) if rms_values else 0.0
        rms_energy_avg = float(np.mean(rms_values)) if rms_values else 0.0

        # Calculate amplitude acceptance rate (frames above threshold)
        amplitude_threshold = self._amplitude_threshold
        accepted_frames = sum(1 for rms in rms_values if rms >= amplitude_threshold)
        amplitude_acceptance_rate = accepted_frames / len(rms_values) if rms_values else 0.0

        # Estimate VAD confidence from recording data (use average RMS as proxy)
        # In production, this would come from VAD node
        vad_confidence = min(1.0, rms_energy_avg / max(0.1, amplitude_threshold))

        metadata = {
            "vad_confidence": vad_confidence,
            "speech_duration": recording_duration,
            "silence_duration": self._silence_threshold,
            "prebuffer_duration": len(list(self._pre_buffer)) * 512 / SAMPLE_RATE,
            "rms_energy_min": rms_energy_min,
            "rms_energy_max": rms_energy_max,
            "rms_energy_avg": rms_energy_avg,
            "amplitude_acceptance_rate": amplitude_acceptance_rate,
            "segment_start_time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self._segment_start_time)) if self._segment_start_time else None,
            "segment_end_time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time())),
        }

        return metadata

    # ------------------------------------------------------------------
    def _send_to_api(self, audio_data: np.ndarray) -> None:
        """Send audio to Orlock API with metadata for intelligent orchestration."""
        if not self._api_client:
            return

        if self.monitor_logger:
            self.monitor_logger.stage_start("SENDING_TO_API")

        try:
            # Collect metadata for orchestration layer
            recording_duration = len(audio_data) / SAMPLE_RATE
            metadata = self._collect_metadata(audio_data, recording_duration)

            self.get_logger().info(
                f'[API] Sending audio with metadata:\n'
                f'  VAD Confidence: {metadata["vad_confidence"]:.3f}\n'
                f'  Speech Duration: {metadata["speech_duration"]:.2f}s\n'
                f'  RMS Energy Avg: {metadata["rms_energy_avg"]:.4f}\n'
                f'  Amplitude Acceptance: {metadata["amplitude_acceptance_rate"]:.1%}'
            )

            # Send to orchestrated endpoint with metadata
            response = self._api_client.send_audio(
                audio_data=audio_data,
                user_id=self._api_user_id,
                system=self._api_system_prompt,
                sample_rate=SAMPLE_RATE,
                metadata=metadata,  # ← NEW: Send metadata for orchestration
            )

            if response['success']:
                msg_text = f'Sent audio - Status: {response["status_code"]}'
                self.get_logger().info(f'[API] {msg_text}')
                if self.monitor_logger:
                    self.monitor_logger.stage_end("SENDING_TO_API")
                    self.monitor_logger.info("API", msg_text)

                # Log enriched response with intent detection
                api_response = response.get('response', {})
                user_text = api_response.get('user_text', '')
                llm_response = api_response.get('llm_response', '')

                # NEW: Log intent detection
                intent = api_response.get('intent', '')
                intent_confidence = api_response.get('intent_confidence', 0.0)
                speech_quality = api_response.get('speech_quality_level', '')
                processing_time = api_response.get('processing_time_ms', 0)

                if user_text:
                    self.get_logger().info(f'[TRANSCRIPTION] {user_text}')
                    if self.monitor_logger:
                        self.monitor_logger.info("WHISPER", user_text)

                if intent:
                    self.get_logger().info(
                        f'[INTENT] {intent} (confidence: {intent_confidence:.2f}, quality: {speech_quality})'
                    )
                    if self.monitor_logger:
                        self.monitor_logger.info("INTENT", f"{intent} ({intent_confidence:.2f})")

                routed_model = api_response.get('routed_model', '')
                if routed_model:
                    self.get_logger().info(f'[MODEL]  → {routed_model}')
                    if self.monitor_logger:
                        self.monitor_logger.info("MODEL", routed_model)

                if llm_response:
                    self.get_logger().info(f'[LLM_RESPONSE] {llm_response}')
                    if self.monitor_logger:
                        self.monitor_logger.info("LLM", llm_response)
                    # Publish response to /orlock/response so tts_node can speak it
                    self._response_pub.publish(String(data=llm_response))

                if processing_time:
                    self.get_logger().info(f'[PERFORMANCE] Processing time: {processing_time:.0f}ms')

                if self.monitor_logger:
                    self.monitor_logger.record_success()
            else:
                msg_text = f'Failed - {response["error"]}'
                self.get_logger().warn(f'[API] {msg_text}')
                if self.monitor_logger:
                    self.monitor_logger.error("API", msg_text)
                    self.monitor_logger.record_error()

        except Exception as exc:
            msg_text = f'Error sending audio: {exc}'
            self.get_logger().error(f'[API] {msg_text}')
            if self.monitor_logger:
                self.monitor_logger.error("API", msg_text, error=str(exc))
                self.monitor_logger.record_error()

    # ------------------------------------------------------------------
    def _save_segment(self) -> None:
        """Concatenate buffered frames, validate, and save as .wav file."""
        if not self._audio_buffer:
            self.get_logger().warn('[SEGMENTATION] Attempted to save empty buffer')
            if self.monitor_logger:
                self.monitor_logger.warning("SEGMENT", "Attempted to save empty buffer")
            return

        # Concatenate all frames
        audio_data = np.concatenate(self._audio_buffer)
        duration = len(audio_data) / SAMPLE_RATE

        # Validate minimum duration
        if duration < self._min_duration:
            msg_text = f'Segment too short ({duration:.2f}s < {self._min_duration}s), skipping'
            self.get_logger().info(f'[SEGMENTATION] {msg_text}')
            if self.monitor_logger:
                self.monitor_logger.info("SEGMENT", msg_text)
            return

        # Generate filename and save
        self._chunk_counter += 1
        filename = f'chunk_{self._chunk_counter}.wav'
        filepath = Path(self._output_dir) / filename

        try:
            # Save as .wav file at 16kHz
            sf.write(str(filepath), audio_data, SAMPLE_RATE)

            msg_text = f'Saved {filename} ({duration:.2f}s, {len(audio_data)} samples)'
            self.get_logger().info(
                f'[SEGMENTATION] Speech ended\n'
                f'  Saved {filename}\n'
                f'  Duration: {duration:.2f}s\n'
                f'  Samples: {len(audio_data)}'
            )
            if self.monitor_logger:
                self.monitor_logger.info("SEGMENT", msg_text)
                # End segment timing
                if self._segment_start_time:
                    segment_duration = (time.time() - self._segment_start_time) * 1000
                    self.monitor_logger.stage_end("RECORDING")

            # --- Send to Orlock API if enabled ----
            if self._enable_api and self._api_client:
                self._send_to_api(audio_data)

        except Exception as exc:
            msg_text = f'Failed to save {filename}: {exc}'
            self.get_logger().error(f'[SEGMENTATION] {msg_text}')
            if self.monitor_logger:
                self.monitor_logger.error("SEGMENT", msg_text, error=str(exc))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SpeechSegmentationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
