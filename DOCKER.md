# CardioQueue

## Quick Start
```bash
docker build -t cardioqueue .
docker run -p 8501:8501 -v "$(pwd)/cardioqueue_data:/app/cardioqueue_data" cardioqueue
```

Open http://localhost:8501

## With docker-compose
```bash
docker-compose up --build
```

## Data Persistence
Patient data is stored in `cardioqueue_data/` (SQLite + JSON files).
The `-v` mount ensures data survives container restarts.
