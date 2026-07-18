# Voice Cognitive Layer

Voice-driven cognitive layer for the GUIDA social robot. This repository contains the ORLOCK server (dialogue and intent orchestration) and a ROS 2 VAD module (voice activity detection and audio segmentation). It connects speech understanding with downstream robot actions (navigation, system control, etc.).

## Features

- Fast local development using Docker Compose

- REST API for orchestration and intent handling

- ROS 2 node for VAD and audio segmentation

## Quick start (Docker)

1. Build and start services:

```bash
docker-compose up --build
```

1. Open the API at [http://localhost:8000](http://localhost:8000) (default) and check docs at [http://localhost:8000/docs](http://localhost:8000/docs)

## Local development (Python)

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

1. Run the ORLOCK API server:

```bash
uvicorn src.orlock.main:app --host 0.0.0.0 --port 8000 --reload
```

## Repository layout

- `orlock-server/` — core orchestration, prompts, intent detection, and API

- `ros2-vad-module/` — ROS 2 package providing VAD and segmentation nodes

- `docker-compose.yml` — quickstart for running the system locally

## Development notes

- Tests live under `orlock-server/tests/` and can be run with `pytest` from the project root (after installing requirements).

- See [orlock-server/README.md](orlock-server/README.md) and [ros2-vad-module/README.md](ros2-vad-module/README.md) for component-specific instructions.

## Contact

- Maintainer: [youssefjaziri](https://github.com/youssefjaziri)

## License

- Check the repository [LICENSE](LICENSE)
