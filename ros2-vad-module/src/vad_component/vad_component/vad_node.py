"""
vad_node.py
-----------
Subscribes to /audio/raw, runs Silero VAD on each chunk, and publishes a
Bool to /speech_detected.

Topics subscribed:
    /audio/raw          (std_msgs/msg/Int16MultiArray)

Topics published:
    /speech_detected    (std_msgs/msg/Bool)

Dependencies (install with pip in your ROS2 environment):
    pip install silero-vad torch
"""

import torch
import sys
from pathlib import Path

from rclpy.node import Node
from std_msgs.msg import Bool, Int16MultiArray

try:
    from silero_vad import load_silero_vad
except ImportError as exc:
    raise ImportError(
        'silero-vad is not installed.  Run:  pip install silero-vad torch'
    ) from exc

import rclpy

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
SAMPLE_RATE = 16_000          # Hz  – must match the publisher
INT16_MAX = 32768.0           # used to normalise int16 → float32 in [-1, 1]
SPEECH_THRESHOLD = 0.5        # Silero VAD confidence threshold


class VadNode(Node):
    """
    Listens to PCM audio chunks and publishes speech-detected events.

    Parameters (ROS2 params):
        threshold (double): VAD confidence threshold [0.0 – 1.0].
                            Default: 0.5
        verbose   (bool):   If True, log every chunk's confidence score.
                            Default: False
    """

    def __init__(self) -> None:
        super().__init__('vad_node')

        # Initialize monitoring logger if available
        self.monitor_logger = None
        if MONITORING_AVAILABLE:
            self.monitor_logger = get_logger()
            self.monitor_logger.info("SYSTEM", "VAD Node starting...")

        # --- declare & read parameters ----------------------------------------
        self.declare_parameter('threshold', SPEECH_THRESHOLD)
        self.declare_parameter('verbose', False)

        self._threshold: float = (
            self.get_parameter('threshold').get_parameter_value().double_value
        )
        self._verbose: bool = (
            self.get_parameter('verbose').get_parameter_value().bool_value
        )

        # --- load Silero VAD model --------------------------------------------
        self.get_logger().info('Loading Silero VAD model …')
        if self.monitor_logger:
            self.monitor_logger.debug("VAD", "Loading Silero model...")
        self._model = load_silero_vad()
        self._model.eval()
        self.get_logger().info('Silero VAD model loaded.')
        if self.monitor_logger:
            self.monitor_logger.info("VAD", "Model loaded")

        # --- subscriber & publisher ------------------------------------------
        self._sub = self.create_subscription(
            Int16MultiArray,
            '/audio/raw',
            self._audio_callback,
            10,
        )
        self._pub = self.create_publisher(Bool, '/speech_detected', 10)

        # Internal state: track previous detection to log edge transitions
        self._last_speech: bool = False

        self.get_logger().info(
            f'VadNode ready – threshold={self._threshold}, verbose={self._verbose}'
        )

    # ------------------------------------------------------------------
    def _audio_callback(self, msg: Int16MultiArray) -> None:
        """Process one audio chunk and publish speech detection result."""
        if not msg.data:
            return

        # Convert int16 PCM → float32 tensor normalised to [-1, 1]
        audio_tensor: torch.Tensor = torch.tensor(
            msg.data, dtype=torch.float32
        ) / INT16_MAX

        # Silero VAD inference  (returns a scalar float in [0, 1])
        with torch.no_grad():
            confidence: float = self._model(audio_tensor, SAMPLE_RATE).item()

        speech_detected: bool = confidence >= self._threshold

        # Publish result
        self._pub.publish(Bool(data=speech_detected))

        # Logging
        if self._verbose:
            self.get_logger().debug(f'VAD confidence: {confidence:.3f}')

        if speech_detected and not self._last_speech:
            msg_text = f'Speech START (confidence={confidence:.3f})'
            self.get_logger().info(f'[VAD] {msg_text}')
            if self.monitor_logger:
                self.monitor_logger.info("VAD", msg_text)
        elif not speech_detected and self._last_speech:
            msg_text = f'Speech END (confidence={confidence:.3f})'
            self.get_logger().info(f'[VAD] {msg_text}')
            if self.monitor_logger:
                self.monitor_logger.info("VAD", msg_text)

        self._last_speech = speech_detected


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VadNode()
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
