# Bonus System / CR Integration Portal — Release 0.2

Backend foundation for the Bitrix24 bonus calculation system.

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy 2 async
- asyncpg
- PostgreSQL 16
- Redis 7
- Alembic
- uv
- Docker Compose

## Start locally

```powershell
cd backend
Copy-Item .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn cr_portal.main:app --reload
```

Swagger:
http://localhost:8000/docs

Health:
- GET /api/v1/health
- GET /api/v1/health/db
- GET /api/v1/health/redis

Bonus calculator:
POST /api/v1/bonus/calculate

## Quality

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```

## Important

The Bitrix24 transport layer is isolated in `backend/src/cr_portal/integrations/bitrix`.
Credentials and real REST synchronization are intentionally not hard-coded.
