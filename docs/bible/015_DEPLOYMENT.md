# 015 — DEPLOYMENT

*Deployment strategy, Docker setup, CI/CD.*

---

## Architecture Overview

```
Client (Browser/Mobile)
         |
         v
    Nginx/Caddy (reverse proxy, TLS)
         |
         v
    FastAPI (Gunicorn + Uvicorn workers)
         |
    +----+----+
    |         |
    v         v
PostgreSQL   Redis
         |
         v
    Celery Workers
```

## Docker Setup

```yaml
# docker-compose.yml services:
#   app: FastAPI application, ports: 8000
#   db: PostgreSQL 16, volume for data
#   redis: Redis 7, volume for data
#   celery: Celery worker, depends on redis + db
#   nginx: Reverse proxy, TLS termination, static files
```

## CI/CD Pipeline

- **GitHub Actions** (or GitLab CI)
- On push to main: lint -> test -> build -> deploy
- Lint: ruff (Python), ESLint (frontend)
- Test: pytest (backend), Jest (frontend)
- Build: Docker image build + push to registry
- Deploy: SSH to server -> docker-compose pull && up
- Health check: /health endpoint returns DB + Redis + Celery status

## Environments

| Environment | Purpose | DB | Deploy Method |
|---|---|---|---|
| local | Development | Local PostgreSQL | docker-compose up |
| staging | Testing | Staging PostgreSQL | Auto-deploy on PR merge |
| production | Live | Production PostgreSQL | Manual deploy after staging tests |

## Monitoring

- Health check: /health endpoint (DB, Redis, Celery)
- Metrics: Prometheus + Grafana (optional)
- Logging: Structured JSON logs to stdout
- Alerts: Email/Slack on service down or error rate > 5%
- Backup: Daily PostgreSQL pg_dump to S3, 30-day retention
