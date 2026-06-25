"""
tts_node.py
-----------
Subscribes to /orlock/response (std_msgs/String) and speaks the text aloud
using pyttsx3 (offline TTS, no cloud dependency).

Publishes /tts/speaking (std_msgs/Bool) while audio is playing so other
nodes can pause listening during playback (avoids echo feedback).

Topics:
    subscribed  /orlock/response   std_msgs/String   — LLM response text
    published   /tts/speaking      std_msgs/Bool     — True while speaking

Parameters:
    enabled      bool   True     — master on/off switch
    voice_rate   int    165      — words per minute
    voice_volume float  0.9      — 0.0 – 1.0
"""

import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class TTSNode(Node):
    def __init__(self):
        super().__init__("tts_node")

        self.declare_parameter("enabled", True)
        self.declare_parameter("voice_rate", 165)
        self.declare_parameter("voice_volume", 0.9)

        self._enabled: bool = self.get_parameter("enabled").value
        self._rate: int = self.get_parameter("voice_rate").value
        self._volume: float = self.get_parameter("voice_volume").value

        self._engine = self._init_engine()
        self._lock = threading.Lock()

        self._sub = self.create_subscription(
            String, "/orlock/response", self._on_response, 10
        )
        self._speaking_pub = self.create_publisher(Bool, "/tts/speaking", 10)

        self.get_logger().info(
            f"TTSNode ready | enabled={self._enabled} "
            f"rate={self._rate} volume={self._volume}"
        )

    # ── engine init ────────────────────────────────────────────────────────────
    def _init_engine(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            self.get_logger().info("pyttsx3 TTS engine initialised")
            return engine
        except Exception as exc:
            self.get_logger().error(
                f"pyttsx3 init failed: {exc}\n"
                "Install with: pip install pyttsx3"
            )
            return None

    # ── callback ───────────────────────────────────────────────────────────────
    def _on_response(self, msg: String) -> None:
        if not self._enabled or not self._engine:
            return
        text = msg.data.strip()
        if not text:
            return
        # Speak in a background thread so ROS2 spin is not blocked
        threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text: str) -> None:
        with self._lock:
            self._publish_speaking(True)
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:
                self.get_logger().error(f"TTS speak error: {exc}")
            finally:
                self._publish_speaking(False)

    def _publish_speaking(self, state: bool) -> None:
        msg = Bool()
        msg.data = state
        self._speaking_pub.publish(msg)
        self.get_logger().debug(f"tts/speaking → {state}")


# ── entry point ────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = TTSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
