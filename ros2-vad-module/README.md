# ROS 2 VAD Module

Voice Activity Detection (VAD) ROS 2 package used to detect speech segments and publish audio segment events to the rest of the system.

## Requirements

- ROS 2 (Humble or compatible distro)

- Colcon build tool

## Build and run (local ROS 2 workspace)

1. From the `ros2-vad-module` folder, create and source your ROS 2 environment and build:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

1. Run the VAD node:

```bash
ros2 run vad_component vad_node
```

## Docker

Build and run a container if you prefer an isolated environment (note: share audio devices as needed):

```bash
docker build -t ros2-vad-module -f ros2-vad-module/Dockerfile .
docker run --rm -it --network host ros2-vad-module
```

## Files

- Node source: `ros2-vad-module/src/vad_component/vad_component/`

- Launch files: `ros2-vad-module/src/vad_component/launch/`

## Notes

- Ensure your host machine has access to audio devices if you plan to test real microphones.

- For CI or headless testing, use the included fake mic node (`fake_mic_node.py`) to simulate audio input.
