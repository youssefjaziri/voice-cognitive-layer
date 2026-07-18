# ORLOCK Server

Lightweight orchestration and intent handling API used by the GUIDA robot. Provides endpoints for message ingestion, intent detection, prompt building, and orchestration services.

## Prerequisites

- Python 3.9+ (3.10 recommended)

- `virtualenv` or `venv` for local development

- Docker (optional, for containerized runs)

## Local development

1. From repository root, create and activate a virtualenv, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

1. Run the API (development mode):

```bash
uvicorn src.orlock.main:app --host 0.0.0.0 --port 8000 --reload
```

1. API docs are available at: [http://localhost:8000/docs](http://localhost:8000/docs)

## Docker

1. Build the image from repository root:

```bash
docker build -t orlock-server -f orlock-server/Dockerfile .
```

1. Run the container:

```bash
docker run --rm -it -p 8000:8000 orlock-server
```

## Testing

- Unit tests are under `orlock-server/tests/`. Run them with `pytest` after installing dependencies.

## Project layout

- `src/orlock/main.py` — FastAPI app entrypoint

- `src/orlock/api/` — API routers and endpoints

- `src/orlock/brain/` — message orchestration and prompt handling

- `src/orlock/intent/` — intent categories and detector

- `src/orlock/knowledge/` — retrieval utilities

## Notes

- Transcription artifacts (if produced) may be written under `transcriptions/`.

- Configuration and credentials (LLM keys, external services) should be set via environment variables or a secrets manager; avoid committing secrets to the repo.
