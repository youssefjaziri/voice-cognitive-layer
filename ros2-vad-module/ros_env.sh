#!/bin/bash
# source this file before running any node in this workspace:
#   source ~/ros2-test/ros_env.sh

ROS_WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source /opt/ros/jazzy/setup.bash
source "$ROS_WS/install/setup.bash"

VENV_DIR=""
if [[ -d "$ROS_WS/venv" ]]; then
	VENV_DIR="$ROS_WS/venv"
elif [[ -d "$ROS_WS/.venv" ]]; then
	VENV_DIR="$ROS_WS/.venv"
fi

if [[ -n "$VENV_DIR" && -f "$VENV_DIR/bin/activate" ]]; then
	source "$VENV_DIR/bin/activate"

	VENV_SITE_PACKAGES="$($VENV_DIR/bin/python - <<'PY'
import site

paths = [p for p in site.getsitepackages() if p.endswith('site-packages')]
print(paths[0] if paths else '')
PY
)"

	if [[ -n "$VENV_SITE_PACKAGES" && ":$PYTHONPATH:" != *":$VENV_SITE_PACKAGES:"* ]]; then
		export PYTHONPATH="$VENV_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
	fi
else
	echo "WARNING: no virtualenv found at '$ROS_WS/venv' or '$ROS_WS/.venv'."
	echo "Create one and install dependencies with:"
	echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
fi

# Route audio through WSLg's built-in PulseAudio socket (Windows mic via RDP)
export PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native

echo "ROS2 Jazzy + vad_component environment ready."
if [[ -n "$VENV_DIR" ]]; then
	echo "  VIRTUALENV : $VENV_DIR"
	echo "  PYTHONPATH : includes venv site-packages"
else
	echo "  VIRTUALENV : not found"
fi
echo "  PULSE_SERVER: WSLg socket → $(PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native pactl info 2>/dev/null | awk '/Default Source/{print $3}' || echo 'unavailable')"
echo ""
echo "  Nodes:"
echo "    ros2 run vad_component mic_node        # live microphone"
echo "    ros2 run vad_component fake_mic_node   # WAV file playback"
echo "    ros2 run vad_component vad_node        # speech detection"
