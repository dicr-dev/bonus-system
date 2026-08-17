# Installation

## Existing local PostgreSQL/Redis

From `backend`:

```powershell
Copy-Item .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn cr_portal.main:app --reload
```

## Docker

From repository root:

```powershell
Copy-Item backend/.env.example backend/.env
docker compose up -d --build
```

Then:

http://localhost:8000/docs
