#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# GIL CLINIC — Mac / Linux Local Setup Script
# One-command install for doctors.
# Usage:  chmod +x setup_local.sh && ./setup_local.sh
# ═══════════════════════════════════════════════════════════════════

set -e

echo ""
echo "🏥 GIL CLINIC — Local Setup"
echo "═══════════════════════════════════"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3.11+ is required. Install from https://python.org"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found."
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt
echo "✅ Dependencies installed."

# Setup database directory
echo ""
echo "🗄️ Setting up database..."
mkdir -p clinic_data

# Create .env if not exists
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# GIL CLINIC Local Environment
GHOS_DB_URL=sqlite:///./clinic_data/clinic.db
GHOS_DB_URL_ASYNC=sqlite+aiosqlite:///./clinic_data/clinic.db
GHOS_DEV_AUTH_BYPASS=true
SECRET_KEY=local-clinic-secret-change-in-production
EOF
    echo "📝 Created .env file."
fi

echo ""
echo "🚀 Starting GIL CLINIC..."
echo "   Open browser: http://localhost:8000"
echo "   Press Ctrl+C to stop."
echo ""

python3 -m uvicorn main_v2:app --host 0.0.0.0 --port 8000 --reload
