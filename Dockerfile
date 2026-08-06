# ─── Dockerfile for CardioQueue (FastAPI) ──────────────────────────────────────
FROM python:3.11-slim

ENV BUILD_CACHE_BUST="2026-08-06T19:15:00"

WORKDIR /app

# Force rebuild trigger — Multi-tenant v2.0 deployment
RUN echo "BUILD: GIL CLINIC v2.0 — $(date)"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Railway injects $PORT dynamically
EXPOSE ${PORT:-8000}

# Fast Health Check endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8000') + '/health')" || exit 1

# Run FastAPI with uvicorn
CMD sh -c "uvicorn main_v2:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
