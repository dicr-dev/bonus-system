# CR Integration Portal — текущее состояние проекта

> Каноническое компактное описание ТЕКУЩЕЙ реализации.
> Текущее рабочее дерево, включая незакоммиченные изменения, имеет приоритет над этим документом.

**Последняя сверка с рабочим деревом:** ЕЩЁ НЕ ВЫПОЛНЕНА

## 1. Назначение продукта

CR Integration Portal — внутреннее веб-приложение для работы с локально синхронизированными данными Bitrix24.

Основные направления:
- синхронизация Bitrix24;
- dashboards и операционная аналитика;
- KPI;
- расчёт бонусов;
- отчёты;
- дальнейшее развитие инструментов поддержки принятия решений.

Аналитика, KPI, отчёты и бонусные расчёты должны использовать локальные данные PostgreSQL, а не постоянно обращаться к Bitrix24.

## 2. Архитектура

```text
Browser
→ Frontend
→ Backend API
→ PostgreSQL / Redis / Bitrix24 REST + OAuth
```

Известный стек:
- Backend: Python, FastAPI, async SQLAlchemy, Alembic, PostgreSQL, Redis, httpx.
- Frontend: React + TypeScript.
- Docker Compose.
- Production reverse proxy: Nginx.
- SSL: Let's Encrypt / Certbot.

Ожидаемые сервисы: backend, frontend, postgres, redis.
PostgreSQL и Redis не должны быть публично доступны в production.

## 3. Структура репозитория

```text
/
├── AGENTS.md
├── PROJECT_STATE.md
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── migrations/
│   └── src/
├── frontend/
│   ├── package.json
│   └── src/
└── docs/
```

Известный backend: `backend/src/cr_portal/`.
Bitrix integration: `backend/src/cr_portal/integrations/bitrix/`.

При сверке исправить эти сведения, если текущий проект уже изменился.

## 4. Bitrix24

Известная реализованная основа:
- OAuth installation;
- access/refresh token persistence;
- refresh истёкшего token;
- синхронизация пользователей;
- получение воронок/categories;
- синхронизация сделок;
- нормализация stages/statuses;
- dashboard активных сделок;
- агрегаты;
- background full sync;
- статус синхронизации.

Известная таблица: `bitrix_installations`.

Ожидаемая auth-цепочка:
```text
installation record
→ client credentials/config
→ access-token validity
→ refresh при необходимости
→ сохранение новых tokens
→ Bitrix API request
```

В истории были `401 Unauthorized` и `wrong_client`. Их ТЕКУЩИЙ статус необходимо подтвердить по коду/runtime.

Secrets и значения tokens в этот файл не записывать.

## 5. Синхронизация

Bitrix24 синхронизируется в PostgreSQL. Обычные reads выполняются по локальной БД.

Длительные/полные синхронизации должны быть background jobs.

Inactive Bitrix users могут быть нужны для исторических mappings.

Нельзя придумывать category IDs, stage IDs, custom/user field IDs и другие portal-specific identifiers.

## 6. Воронки и сделки

Известные рабочие воронки:
- `CR Start`;
- `Внедрение`;
- `Сопровождение`;
- `Тех интеграция`.

Active/inactive определяется по фактической семантике Bitrix stages / нормализованным статусам.

Исторические количества сделок — snapshots, а не константы.

## 7. Ответственный за внедрение

Ключевой бизнес-концепт:
`Ответственный за внедрение`.

Он не равен автоматически Bitrix `assignedById`.

Известное нормализованное поле:
`implementation_responsible_user_id`.

Точный текущий mapping Bitrix-поля подтвердить при сверке.

## 8. KPI и бонусы

KPI и bonus calculations работают по локальным синхронизированным данным.

Business rules должны поддерживать versioning там, где требуется историческая корректность.

Исторические KPI/results должны сохранять исторический смысл, а не полностью пересчитываться только по сегодняшним правилам.

### Требуется заполнить из текущего кода

При первичной сверке описать на уровне бизнес-поведения:
- текущие формулы;
- периоды;
- исключения;
- thresholds;
- правила расчёта;
- versioning;
- историческое поведение.

Не придумывать отсутствующие правила.

## 9. База данных

PostgreSQL + async SQLAlchemy + Alembic.

Persistent schema changes выполняются через Alembic. Старые применённые migrations не переписываются.

Известная таблица: `bitrix_installations`.

### Требуется заполнить из текущего кода

Добавить основные domain tables/models:
- назначение;
- ключевые связи;
- важные бизнес-поля;
- исторические/versioning особенности.

Не превращать файл в полный database dictionary.

## 10. Backend

Известные зоны:
- HTTP API;
- services/business logic;
- persistence;
- Bitrix integration;
- synchronization;
- background jobs;
- KPI/bonus/reports.

### Текущий API
**Требуется сверка с рабочим деревом.**

Зафиксировать основные endpoint groups и важные контракты, не обязательно каждый route.

## 11. Frontend

Стек: React + TypeScript.

### Текущие страницы и процессы
**Требуется сверка с рабочим деревом.**

Добавить фактически реализованные основные pages и user flows.

## 12. Background jobs

Известны full Bitrix sync и sync-status tracking.

### Требуется сверка
Проверить:
- механизм jobs;
- queue/scheduler;
- locking/concurrency;
- retry/error behavior;
- гранулярность синхронизации.

## 13. Конфигурация

Secrets находятся в environment configuration и не коммитятся.

В этом файле можно хранить имена важных environment variables и их назначение, но не секретные значения.

### Важная текущая конфигурация
**Требуется сверка с рабочим деревом.**

## 14. Deployment

Исторический production path: `/opt/cr-portal/`.

Исторически использовались `git pull`, Docker Compose build/up и Alembic upgrade.

Текущий branch и deployment procedure должны быть проверены перед тем, как считать их актуальными.

## 15. Реализованная функциональность

Известная основа:
- Bitrix OAuth;
- token persistence/refresh;
- user sync;
- funnels/categories;
- deal sync;
- stage/status normalization;
- local PostgreSQL storage;
- active-deal dashboard;
- aggregates;
- background sync/status.

**Обязательно дополнить/исправить после проверки текущего рабочего дерева.**

Все уже сделанные Codex изменения, присутствующие в текущем коде, должны попасть сюда или в соответствующие тематические разделы.

## 16. Сейчас в разработке

**Требуется сверка.**

Добавлять только реально незавершённую продуктовую работу, подтверждённую кодом или явно согласованным планом. Не считать каждый TODO утверждённой задачей.

## 17. Известные пробелы / неопределённости

До первой сверки:
- последние локальные изменения Codex могут ещё отсутствовать в документе;
- точные KPI/bonus rules ещё не зафиксированы;
- полный список основных domain models не зафиксирован;
- текущий API/page inventory не зафиксирован;
- статус `wrong_client` не подтверждён;
- production branch/deployment procedure не подтверждён.

После проверки удалять решённые пункты.

## 18. Подтверждённые решения

- аналитика использует локально синхронизированные данные Bitrix;
- `Ответственный за внедрение` — отдельный бизнес-концепт от `assignedById`;
- длительные синхронизации — background jobs;
- inactive users могут быть нужны для истории;
- исторические KPI/results сохраняют исторический смысл;
- business rules поддерживают versioning там, где это требуется;
- Bitrix IDs и бизнес-правила нельзя придумывать;
- более поздние подтверждённые решения приоритетнее старой истории.

## 19. Правила поддержки файла

Это описание ТЕКУЩЕГО СОСТОЯНИЯ, а не changelog.

При изменении логики старое описание заменяется новым. Git хранит историю.

Обновлять после существенных изменений архитектуры, data model, APIs, Bitrix integration, KPI/bonus, reports, frontend flows, deployment/runtime, известных проблем и статуса крупных функций.

Файл должен оставаться компактным.

## 20. Команда первичной сверки

После добавления файлов в корень проекта открыть новый Codex-чат и выполнить:

```text
Актуализируй PROJECT_STATE.md по текущему состоянию проекта.

Следуй AGENTS.md.

Важно:
- источник истины — текущее рабочее дерево;
- обязательно учти незакоммиченные изменения;
- сначала выполни git status и проверь релевантный git diff;
- не полагайся только на старое ТЗ;
- старые документы используй только для понимания бизнес-смысла;
- не изменяй код приложения;
- обновляй только PROJECT_STATE.md;
- проверь основные backend/frontend модули, модели, Alembic migrations,
  Bitrix integration, jobs и текущую KPI/bonus бизнес-логику;
- не сканируй vendor/cache/generated directories без необходимости;
- удаляй устаревшие сведения;
- не добавляй секреты;
- неподтверждённое помещай в «Известные пробелы / неопределённости».

В конце кратко перечисли:
1. какие разделы PROJECT_STATE.md актуализированы;
2. какие новые функции и бизнес-правила найдены;
3. что осталось неподтверждённым.
```

После успешной сверки заменить:
`Последняя сверка с рабочим деревом: ЕЩЁ НЕ ВЫПОЛНЕНА`
на фактическую дату.
