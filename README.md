# voice-cognitive-layer

Voice-driven cognitive layer for the GUIDA social robot. This repository contains the ORLOCK server (dialogue, intent orchestration) and a ROS2 VAD module used for speech activity detection and segmentation. It ties speech understanding with robot actions such as navigation.

Contents
- orlock-server: core orchestration and intent handling services
- ros2-vad-module: ROS2 node for voice activity detection and audio segmentation
- docker-compose.yml and supporting configs to run services locally

Quickstart
- See QUICKSTART.md for full setup and run instructions.
- Typical workflow: run docker-compose, start the ORLOCK server, and bring up the ROS2 VAD node for audio input.

Notes
- The repository mirrors the original work hosted at the university Git server. Demo or temporary files may be present locally and are not always pushed to GitHub.

Contact
- Maintainer: youssefjaziri (https://github.com/youssefjaziri)

