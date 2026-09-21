FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects PORT (10000 by default) and expects the process to bind it.
# The default keeps `docker compose up` and the nginx upstream working unchanged.
ENV PORT=8000

# WEB_CONCURRENCY=1 is deliberate, not just a memory concession to the 512MB
# free tier: app/main.py starts an AsyncIOScheduler per process, so N workers
# means N copies of every interval job (order progression, stale-op auto-fail)
# racing on the same rows. Raising this requires moving the scheduler out of
# the worker first.
ENV WEB_CONCURRENCY=1

# Shell form so ${PORT} / ${WEB_CONCURRENCY} are expanded at runtime.
# --forwarded-allow-ips "*" trusts X-Forwarded-* from the front proxy (nginx
# locally, Render's edge in production) so request.client.host is the real
# client IP — required for per-client rate limiting.
# `exec` replaces the shell so gunicorn becomes PID 1 and receives SIGTERM
# directly — without it /bin/sh swallows the signal and the shutdown hook that
# stops the scheduler (app/main.py:609) never runs before Render hard-kills.
CMD exec gunicorn app.main:app \
      --workers ${WEB_CONCURRENCY} \
      --worker-class uvicorn.workers.UvicornWorker \
      --bind 0.0.0.0:${PORT} \
      --timeout 120 \
      --forwarded-allow-ips "*" \
      --access-logfile - \
      --error-logfile -
