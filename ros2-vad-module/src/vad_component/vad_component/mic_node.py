"""
mic_node.py
-----------
Captures audio from the default system microphone and publishes 512-sample
chunks to /audio/raw at real-time rate.

This is a drop-in replacement for fake_mic_node: the topic name, message
type, and chunk size are identical, so the VAD node requires no changes.

Topic published:
    /audio/raw  (std_msgs/msg/Int16MultiArray)
        - CHUNK_SAMPLES int16 PCM samples per message.
        - Mono, 16 kHz.

Dependencies:
    pip install sounddevice   (already in the venv)

Parameters (ROS2 params):
    device      (int | str): Input device index or substring of its name.
                             -1 / "" means the system default (default).
    chunk_size  (int):       Samples per chunk. Must be 256, 512, or 1024
                             for Silero VAD at 16 kHz. Default: 512.
"""

import queue
import threading

import numpy as np
import sounddevice as sd

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16MultiArray, MultiArrayDimension, MultiArrayLayout

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16_000       # Hz
CHUNK_SAMPLES = 512        # samples per chunk  → 32 ms at 16 kHz
INT16_MAX = 32767


class MicNode(Node):
    """
    Publishes live microphone audio to /audio/raw.

    sounddevice fills an internal queue from a low-latency audio thread;
    the ROS2 timer drains the queue and publishes – keeping audio I/O
    and ROS2 publishing on separate threads.
    """

    def __init__(self) -> None:
        super().__init__('mic_node')

        # --- parameters -------------------------------------------------------
        self.declare_parameter('device', 'pulse')   # 'pulse' → PulseAudio default (works on WSL2 + native Linux)
        self.declare_parameter('chunk_size', CHUNK_SAMPLES)

        device_param: str = self.get_parameter('device').get_parameter_value().string_value
        self._chunk: int = self.get_parameter('chunk_size').get_parameter_value().integer_value

        # Resolve device: empty string → None (sounddevice default)
        device = None
        if device_param.strip():
            # Try integer index first, then treat as name substring
            try:
                device = int(device_param)
            except ValueError:
                device = device_param

        # --- audio queue (thread-safe) ----------------------------------------
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()

        # --- publisher --------------------------------------------------------
        self._pub = self.create_publisher(Int16MultiArray, '/audio/raw', 10)

        dim = MultiArrayDimension(
            label='samples',
            size=self._chunk,
            stride=self._chunk,
        )
        self._layout = MultiArrayLayout(dim=[dim], data_offset=0)

        # --- open InputStream -------------------------------------------------
        # blocksize=chunk means the callback fires exactly every chunk samples.
        # dtype='float32' keeps conversion simple; we scale to int16 before pub.
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocksize=self._chunk,
                device=device,
                callback=self._audio_callback,
            )
            self._stream.start()
        except sd.PortAudioError as exc:
            self.get_logger().fatal(f'Failed to open microphone: {exc}')
            raise

        # Timer fires at the same rate as audio chunks arrive
        chunk_duration = self._chunk / SAMPLE_RATE
        self._timer = self.create_timer(chunk_duration, self._publish_chunk)

        dev_name = self._stream.device
        self.get_logger().info(
            f'MicNode ready – device={dev_name}, '
            f'{SAMPLE_RATE} Hz, {self._chunk}-sample chunks → /audio/raw'
        )

    # ------------------------------------------------------------------
    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice in a dedicated audio thread."""
        if status:
            self.get_logger().warn(f'Audio stream status: {status}')
        # indata shape: (frames, 1) – squeeze to 1-D, put a copy in the queue
        self._q.put_nowait(indata[:, 0].copy())

    # ------------------------------------------------------------------
    def _publish_chunk(self) -> None:
        """Drain one chunk from the queue and publish it."""
        try:
            frames: np.ndarray = self._q.get_nowait()
        except queue.Empty:
            return  # audio not ready yet – skip this timer tick

        # float32 [-1, 1] → int16
        samples_int16: np.ndarray = np.clip(
            frames * INT16_MAX, -INT16_MAX - 1, INT16_MAX
        ).astype(np.int16)

        msg = Int16MultiArray(layout=self._layout, data=samples_int16.tolist())
        self._pub.publish(msg)

    # ------------------------------------------------------------------
    def destroy_node(self) -> None:
        self._stream.stop()
        self._stream.close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MicNode()
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
