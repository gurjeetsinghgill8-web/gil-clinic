# ─── Dockerfile for CardioQueue (FastAPI) ──────────────────────────────────────
FROM python:3.11-slim

ENV BUILD_CACHE_BUST="2026-08-08T19:45:00"

WORKDIR /app

# Force rebuild trigger — Multi-tenant v2.0 deployment
RUN echo "BUILD: GIL CLINIC v2.0 + EasyOCR — $(date)"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
# Install CPU-only PyTorch first (smaller than full torch)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR model (English) during build
RUN python -c "import easyocr; reader = easyocr.Reader(['en'], gpu=False, verbose=False); print('EasyOCR model downloaded OK')"

# Copy application
COPY . .

# Railway injects $PORT dynamically
EXPOSE ${PORT:-8000}

# Fast Health Check endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8000') + '/health')" || exit 1

# Run FastAPI with uvicorn
CMD sh -c "uvicorn main_v2:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
