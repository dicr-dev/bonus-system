# CR Integration Portal — полное KPI/Bonus обновление

Пакет накладывается поверх текущего проекта. PostgreSQL не удалять.

## Реализовано
- статусы: process→in_progress, success→won, failure/apology→lost;
- ответственный по полю «Ответственный за внедрение»;
- версионируемые правила и расчеты;
- Тех интеграция 50%;
- Внедрение 3 месяца, пороги 10/11/12/13/15%;
- CR Start: фикс 10 000 или как внедрение после настройки реальных CR Start полей;
- Продажа 10% после настройки реального поля сотрудника;
- сопровождение по часам и обучение через ручные события до подключения TBD-полей задач;
- текущие клиенты после настройки реальной связи и определения «клиент работает»;
- делитель 2.5 и исключения;
- KPI отдела = Внедрение + CR Start, исторические KPI events;
- план/факт/остаток/выполнение/потенциал/прогноз;
- диагностика;
- Excel: Общий отчет / Детализация / Ошибки;
- frontend разделы: Главная, KPI отдела, Расчет премий, Сделки, Диагностика, Правила, Синхронизация.

## TBD: НЕ угадывать
В backend/.env заполнить после получения из фактической схемы Bitrix24:
BITRIX_FIELD_SOURCE_DEAL_ID=
BITRIX_FIELD_SALES_BONUS_USER_ID=
BITRIX_CR_START_BOOLEAN_FIELDS=
BITRIX_FIELD_CLIENT_WORKS=
BITRIX_TASK_TRAINING_BONUS_FIELD=

## Локальная проверка
cd C:\Users\cruser\Documents\GitHub\bonus-system-prod\backend
uv sync
uv run python -m compileall -q src
uv run pytest
cd ..\frontend
npm.cmd install
npm.cmd run build

Если Dockerfile frontend использует готовый dist:
cd ..
git add backend frontend/src README_INSTALL.md
git add -f frontend/dist
git commit -m "Implement KPI and bonus application"
git push origin develop

## Production: обязательно backup
cd /opt/cr-portal
docker compose exec -T postgres pg_dump -U cr_portal -d cr_portal > /root/cr_portal_before_kpi.sql

git pull origin develop
docker compose up -d --build backend worker
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade head
docker compose restart backend worker

Ожидаемый head:
0004_kpi_bonus

Синхронизация:
curl -X POST https://integration.crmicro.ru/api/v1/sync/users
curl -X POST "https://integration.crmicro.ru/api/v1/sync/deals?full=true"

Диагностика:
curl -X POST "https://integration.crmicro.ru/api/v1/diagnostics/run?month=2026-08"

KPI:
curl "https://integration.crmicro.ru/api/v1/kpi/summary?month=2026-08"

План:
curl -X PUT "https://integration.crmicro.ru/api/v1/kpi/plan?month=2026-08" -H "Content-Type: application/json" -d '{"plan_value":20,"comment":"План отдела"}'

Расчет:
curl -X POST "https://integration.crmicro.ru/api/v1/calculations/run?month=2026-08"

Excel:
https://integration.crmicro.ru/api/v1/reports/export/excel?month=2026-08
