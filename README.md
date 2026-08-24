# CR Integration Portal 1.0.0

Консолидированный релиз приложения: FastAPI, PostgreSQL, Redis, Bitrix24, отчёты, KPI/бонусы, распределение сделок и React frontend.

## Установка с нуля

```powershell
Copy-Item backend\.env.example backend\.env
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Открыть:
- http://localhost:3000
- http://localhost:8000/docs

Baseline Alembic: одна миграция `0001_baseline`.
