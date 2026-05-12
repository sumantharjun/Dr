# Smart Baby Feeding — Backend

FastAPI + SQLAlchemy + MySQL backend.

## Prerequisites

- Python 3.11+
- MySQL running locally, or via `docker-compose up -d db` from the project root

## Setup

From the `backend/` directory:

```bash
# Activate the project venv
source Dr/bin/activate

# Install dependencies (first time only, or after requirements.txt changes)
pip install -r requirements.txt
```

## Run (development)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

## Run (production-style)

Matches the Dockerfile `CMD`:

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

## Run via Docker Compose

From the project root:

```bash
docker-compose up backend
```

## Configuration

Database and other settings are read from environment variables in `app/config.py`. See `../docker-compose.env.example` for the available keys.
