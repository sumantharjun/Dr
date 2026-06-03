FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Production default — overridden in docker-compose if needed
# --forwarded-allow-ips "*" trusts X-Forwarded-* from the front proxy (nginx) so
# request.client.host is the real client IP — required for per-client rate
# limiting. Tighten "*" to the proxy's IP/subnet if exposed beyond nginx.
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--forwarded-allow-ips", "*", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
