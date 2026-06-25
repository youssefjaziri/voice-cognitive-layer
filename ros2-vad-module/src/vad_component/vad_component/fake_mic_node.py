"""
fake_mic_node.py
----------------
Reads a mono 16 kHz WAV file and publishes its audio chunks to /audio/raw
at the correct real-time rate, simulating a live microphone stream.

Supports any WAV subtype (int16, int24, float32, …) – samples are always
converted to int16 before publishing.

Topic published:
    /audio/raw  (std_msgs/msg/Int16MultiArray)
        - Each message carries CHUNK_SAMPLES int16 PCM samples.
        - layout.dim[0].label  = "samples"
        - layout.dim[0].size   = CHUNK_SAMPLES
        - layout.dim[0].stride = CHUNK_SAMPLES
        - layout.data_offset   = 0

Design note:
    The only thing that changes when you swap this node for a real microphone
    is the audio *source* (wav file → pyaudio/sounddevice stream).  The
    published message format and topic name stay identical, so the VAD node
    needs no modifications.
"""

import os

import numpy as np
import soundfile as sf

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16MultiArray, MultiArrayDimension, MultiArrayLayout

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16_000          # Hz  – must match the WAV file
CHUNK_SAMPLES = 512           # samples per chunk  → ~32 ms at 16 kHz
# Silero VAD requires exactly 256, 512, or 1024 samples at 16 kHz.
CHUNK_DURATION_SEC = CHUNK_SAMPLES / SAMPLE_RATE   # ≈ 0.032 s
INT16_MAX = 32767


class FakeMicNode(Node):
    """
    Publishes PCM audio chunks read from a WAV file to /audio/raw.

    Parameters (ROS2 params):
        audio_file (str): Absolute or relative path to the .wav file.
                          Relative paths are resolved from the current
                          working directory.
        loop (bool):      If True (default), replay the file indefinitely.
    """

    def __init__(self) -> None:
        super().__init__('fake_mic_node')

        # --- declare & read parameters ----------------------------------------
        self.declare_parameter('audio_file', 'audio.wav')
        self.declare_parameter('loop', True)

        audio_file: str = self.get_parameter('audio_file').get_parameter_value().string_value
        self._loop: bool = self.get_parameter('loop').get_parameter_value().bool_value

        audio_file = os.path.expanduser(audio_file)
        if not os.path.isabs(audio_file):
            audio_file = os.path.join(os.getcwd(), audio_file)

        # --- open & validate WAV file via soundfile ---------------------------
        # soundfile supports all WAV subtypes: PCM-16, PCM-24, float32, etc.
        if not os.path.isfile(audio_file):
            self.get_logger().fatal(f'Audio file not found: {audio_file}')
            raise FileNotFoundError(audio_file)

        info = sf.info(audio_file)
        assert info.channels == 1, \
            f'{audio_file}: expected mono, got {info.channels} channels'
        assert info.samplerate == SAMPLE_RATE, \
            f'{audio_file}: expected {SAMPLE_RATE} Hz, got {info.samplerate} Hz'

        # Open for block-by-block reading; always read as float32, convert below
        self._sf = sf.SoundFile(audio_file, mode='r')
        self._audio_file = audio_file

        self.get_logger().info(
            f'Opened "{audio_file}" [{info.subtype}, {info.samplerate} Hz, '
            f'{info.channels}ch, {info.frames} frames]'
        )

        # --- publisher --------------------------------------------------------
        self._pub = self.create_publisher(Int16MultiArray, '/audio/raw', 10)

        # --- reusable message layout ------------------------------------------
        dim = MultiArrayDimension(
            label='samples',
            size=CHUNK_SAMPLES,
            stride=CHUNK_SAMPLES,
        )
        self._layout = MultiArrayLayout(dim=[dim], data_offset=0)

        # --- timer  (fires every CHUNK_DURATION_SEC seconds) ------------------
        self._timer = self.create_timer(CHUNK_DURATION_SEC, self._publish_chunk)

        self.get_logger().info(
            f'FakeMicNode ready – publishing as {CHUNK_SAMPLES}-sample chunks '
            f'on /audio/raw (loop={self._loop})'
        )

    # ------------------------------------------------------------------
    def _publish_chunk(self) -> None:
        # Read as float32 in [-1.0, 1.0] regardless of source subtype
        frames: np.ndarray = self._sf.read(
            CHUNK_SAMPLES, dtype='float32', always_2d=False
        )

        # End-of-file handling
        if len(frames) < CHUNK_SAMPLES:
            if self._loop:
                self._sf.seek(0)
                remainder = self._sf.read(
                    CHUNK_SAMPLES - len(frames), dtype='float32', always_2d=False
                )
                frames = np.concatenate([frames, remainder])
                self.get_logger().debug('WAV file looped.')
            else:
                self.get_logger().info('End of audio file – shutting down.')
                self._timer.cancel()
                rclpy.shutdown()
                return

        # Convert float32 → int16  (clip to avoid overflow)
        samples_int16: np.ndarray = np.clip(
            frames * INT16_MAX, -INT16_MAX - 1, INT16_MAX
        ).astype(np.int16)

        msg = Int16MultiArray(layout=self._layout, data=samples_int16.tolist())
        self._pub.publish(msg)

    # ------------------------------------------------------------------
    def destroy_node(self) -> None:
        self._sf.close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FakeMicNode()
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
