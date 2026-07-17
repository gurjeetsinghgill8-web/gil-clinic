# ─── Dockerfile for CardioQueue (FastAPI) ──────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8000'))" || exit 1

# Run FastAPI with uvicorn — works perfectly on mobile networks (no WebSocket issues)
CMD sh -c "uvicorn main_v2:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
