# ros2-VAD-module

## Launch The Project

### 1) Local run (ROS 2 workspace)
```bash
# from repository root
source /opt/ros/humble/setup.bash
source install/setup.bash

# run the VAD node
ros2 run vad_component vad_node
```

### 2) Docker run
```bash
# build image
docker build -t ros2-vad-module .

# run container
docker run --rm -it --network host ros2-vad-module
```

## Notes
- Ensure ROS 2 Humble is installed for local execution.
- The node code is under `src/vad_component/vad_component/`.
