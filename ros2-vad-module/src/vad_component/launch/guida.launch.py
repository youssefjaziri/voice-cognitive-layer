"""
GUIDA Robot — full pipeline launch file.
Starts all four nodes in order: mic → vad → segmentation → tts

Usage (from ros2-VAD-module, after sourcing ros_env.sh):
    ros2 launch vad_component guida.launch.py

Optional overrides:
    ros2 launch vad_component guida.launch.py api_url:=http://192.168.1.10:8000
    ros2 launch vad_component guida.launch.py tts_enabled:=false
    ros2 launch vad_component guida.launch.py vad_threshold:=0.6
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    # ── launch arguments (can be overridden on the command line) ─────────────
    args = [
        DeclareLaunchArgument(
            "api_url",
            default_value="http://localhost:8000",
            description="Orlock FastAPI server URL",
        ),
        DeclareLaunchArgument(
            "api_user_id",
            default_value="guida_user",
            description="User ID sent with every API request",
        ),
        DeclareLaunchArgument(
            "vad_threshold",
            default_value="0.5",
            description="Silero VAD probability threshold (0.0–1.0)",
        ),
        DeclareLaunchArgument(
            "silence_threshold",
            default_value="1.5",
            description="Seconds of silence before a segment is finalised",
        ),
        DeclareLaunchArgument(
            "tts_enabled",
            default_value="true",
            description="Enable TTS voice output (true/false)",
        ),
        DeclareLaunchArgument(
            "tts_rate",
            default_value="165",
            description="TTS speaking rate (words per minute)",
        ),
    ]

    # ── node 1: microphone capture ────────────────────────────────────────────
    mic_node = Node(
        package="vad_component",
        executable="mic_node",
        name="mic_node",
        output="screen",
        emulate_tty=True,
    )

    # ── node 2: VAD inference (slight delay so mic is ready first) ────────────
    vad_node = TimerAction(
        period=1.0,
        actions=[
            Node(
                package="vad_component",
                executable="vad_node",
                name="vad_node",
                output="screen",
                emulate_tty=True,
                parameters=[
                    {"threshold": LaunchConfiguration("vad_threshold")},
                ],
            )
        ],
    )

    # ── node 3: speech segmentation + Orlock API client ───────────────────────
    segmentation_node = TimerAction(
        period=2.0,
        actions=[
            Node(
                package="vad_component",
                executable="speech_segmentation_node",
                name="speech_segmentation_node",
                output="screen",
                emulate_tty=True,
                parameters=[
                    {"enable_api":         True},
                    {"api_url":            LaunchConfiguration("api_url")},
                    {"api_user_id":        LaunchConfiguration("api_user_id")},
                    {"silence_threshold":  LaunchConfiguration("silence_threshold")},
                    {"pre_buffer_duration": 1.0},
                    {"enable_amplitude_filter": True},
                ],
            )
        ],
    )

    # ── node 4: text-to-speech output ─────────────────────────────────────────
    tts_node = TimerAction(
        period=2.0,
        actions=[
            Node(
                package="vad_component",
                executable="tts_node",
                name="tts_node",
                output="screen",
                emulate_tty=True,
                parameters=[
                    {"enabled":      LaunchConfiguration("tts_enabled")},
                    {"voice_rate":   LaunchConfiguration("tts_rate")},
                    {"voice_volume": 0.9},
                ],
            )
        ],
    )

    log_start = LogInfo(msg=">>> GUIDA pipeline starting — waiting for Orlock server at http://localhost:8000")

    return LaunchDescription(args + [log_start, mic_node, vad_node, segmentation_node, tts_node])
