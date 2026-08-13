# CR Integration Portal Backend

FastAPI + SQLAlchemy async + PostgreSQL + Redis.

## Local development

```powershell
uv sync
Copy-Item .env.example .env
uv run alembic upgrade head
uv run uvicorn cr_portal.main:app --reload
```

Swagger: http://localhost:8000/docs

Health:
- GET /api/v1/health
- GET /api/v1/health/db
- GET /api/v1/health/redis

## Quality

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```
