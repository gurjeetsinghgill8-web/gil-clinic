# ─── Dockerfile for CardioQueue ────────────────────────────────────────────────
# Build & run:
#   docker build -t cardioqueue .
#   docker run -p 8501:8501 -v "$(pwd)/cardioqueue_data:/app/cardioqueue_data" cardioqueue
# ────────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for qrcode/pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Railway injects $PORT — expose it dynamically
EXPOSE ${PORT:-8501}

# Health check using Railway's dynamic port
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8501'))" || exit 1

# Run Streamlit with mobile-network-safe flags:
#   --server.port=$PORT         → Railway's dynamic port
#   --server.address=0.0.0.0   → Accept connections from all interfaces
#   --server.enableCORS=false  → Mobile carrier proxy compatibility
#   --server.enableWebsocketCompression=false → Fixes Jio/Airtel mobile data issues
CMD sh -c "streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --server.enableWebsocketCompression=false \
    --server.headless=true \
    --browser.gatherUsageStats=false"
