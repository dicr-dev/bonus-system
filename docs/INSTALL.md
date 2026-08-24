# Чистая установка

```powershell
Copy-Item backend\.env.example backend\.env
docker compose down -v --remove-orphans
docker compose up -d --build
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade head
docker compose exec backend pytest
```

`alembic heads` должен показать только `0001_baseline (head)`.