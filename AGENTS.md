# AGENTS.md — CR Integration Portal

## Purpose

This repository contains **CR Integration Portal**.

The system is not just a bonus calculator. It is an internal web application built around locally synchronized Bitrix24 data and is intended to support:

- Bitrix24 data synchronization;
- implementation department dashboards;
- employee workload and deal analytics;
- KPI;
- bonus calculations;
- reports;
- administration;
- future decision-support features.

When older documentation conflicts with newer implementation or newer specifications, **prefer the newest confirmed behavior**.

---

## Communication

- Communicate with the user in **Russian** unless explicitly asked otherwise.
- Keep explanations concise and practical.
- When a task is complete, report:
  1. what was changed;
  2. which files were changed;
  3. how it was verified;
  4. whether migrations or deployment actions are required.
- Do not explain obvious code line-by-line unless requested.

---

# 1. Context and resource efficiency

The primary goal is to solve the requested task correctly while using as little repository context and compute as reasonably possible.

## Mandatory rules

- **Do not scan the entire repository by default.**
- Start with files directly related to the user's task.
- Use targeted filename/code search before opening large files.
- Do not recursively inspect unrelated directories.
- Do not reread files already inspected unless needed.
- Do not investigate unrelated warnings, TODOs, style issues, or bugs.
- Do not perform broad refactors unless explicitly requested or required for correctness.
- Prefer the **smallest correct change**.
- Reuse existing project patterns instead of researching alternative architectures.
- Do not open generated files, build output, caches, dependencies, or lockfiles unless specifically needed.
- Avoid reading large logs in full. Start with the smallest useful tail/filter.
- Avoid dumping full database tables. Query only relevant columns/rows.
- Avoid repeated Docker rebuilds when a narrower verification is sufficient.
- Do not run full test suites when targeted tests are enough.
- Before broad repository exploration, state briefly why it is necessary.

## Search strategy

Use this order:

1. identify likely module/file;
2. search for the exact symbol, endpoint, table, setting, or error;
3. inspect the smallest relevant code region;
4. trace only direct dependencies;
5. modify only necessary files;
6. run the narrowest useful validation.

If the task names an endpoint, class, table, error message, environment variable, Bitrix method, or UI component, search for that exact identifier first.

## Stop conditions

Stop exploring when enough information exists to make a safe change.

Do not continue searching merely to gain additional confidence after the relevant execution path is already understood.

---

# 1A. Task cost mode

Before doing substantial work, classify the task internally into one of three modes.

Do not spend tokens explaining this classification to the user unless it is useful.

## ECONOM

Use for:

- locating a file, symbol, endpoint, setting, or error;
- small UI/text changes;
- simple typing/syntax fixes;
- small isolated backend/frontend changes;
- reading a short log;
- simple SQL diagnostics;
- targeted tests;
- git diff/status inspection.

Behavior:

- inspect only directly relevant files;
- prefer exact search;
- no repository-wide scan;
- no broad architectural analysis;
- no full test suite;
- no Docker rebuild unless directly required;
- no unrelated cleanup;
- implement immediately when the change is obvious and safe.

Target workflow:

```text
exact search
-> 1-3 relevant files
-> minimal change
-> targeted check
-> stop
```

## NORMAL

This is the default for normal feature development and bug fixing.

Use for:

- regular bug fixes;
- API endpoints;
- CRUD;
- Bitrix synchronization changes;
- small/medium migrations;
- dashboard changes;
- background jobs;
- normal business logic;
- moderate refactoring.

Behavior:

- inspect the narrow execution path first;
- follow only direct dependencies;
- make a short plan only when useful;
- keep the diff small;
- run affected tests/checks;
- expand investigation only when evidence requires it.

Target workflow:

```text
targeted search
-> understand affected path
-> short plan if needed
-> focused implementation
-> affected tests
-> stop
```

## COMPLEX

Use only when complexity or risk genuinely requires broader reasoning.

Examples:

- architectural redesign;
- concurrency/race conditions;
- data corruption or consistency issues;
- complex PostgreSQL migrations;
- major OAuth/token-flow redesign;
- cross-module business-rule redesign;
- difficult production-only failures;
- large new subsystems.

Behavior:

- first define the failure/goal precisely;
- inspect relevant architecture before coding;
- explicitly identify data-safety and compatibility risks;
- broaden repository exploration only as necessary;
- prefer a staged implementation;
- use broader tests only after targeted checks pass.

COMPLEX does **not** mean "scan everything".

Even in COMPLEX mode, repository exploration must remain evidence-driven.

---

## Escalation policy

Always start at the cheapest mode that can safely solve the task.

Preferred progression:

```text
ECONOM -> NORMAL -> COMPLEX
```

Do not jump directly to COMPLEX merely because:

- the repository is large;
- Bitrix24 is involved;
- Docker is involved;
- the task mentions production;
- a test failed once.

Escalate only when the current mode is insufficient.

Valid reasons to escalate include:

- the failure crosses multiple modules;
- the root cause remains ambiguous after targeted inspection;
- schema/data compatibility is at risk;
- concurrency is involved;
- a public API contract must change;
- multiple plausible fixes have significant tradeoffs.

Before substantially broadening exploration, briefly state the reason.

---

## De-escalation policy

After the difficult part is understood, return to narrow execution.

Example:

```text
COMPLEX investigation
-> root cause found
-> NORMAL implementation
-> ECONOM targeted verification
```

Do not keep operating in a broad investigation mode after the root cause is known.

---

## Tool-call budget mindset

Every repository read, search, command, test, build, and log request should answer a concrete question.

Before a potentially expensive action, ask internally:

```text
What specific uncertainty will this action resolve?
```

If there is no concrete answer, skip the action.

Prefer:

```text
search exact symbol
```

over:

```text
list/read many directories
```

Prefer:

```text
targeted test
```

over:

```text
entire test suite
```

Prefer:

```text
docker compose logs --tail=100 backend
```

over:

```text
all Docker logs
```

Prefer:

```text
SELECT needed_columns FROM relevant_table WHERE ...
```

over:

```text
SELECT * from large tables
```

---

## Context budget

Keep active context small.

- Summarize findings instead of repeatedly reopening the same files.
- Remember relevant paths/symbols discovered during the current task.
- Do not reread unchanged code without a reason.
- When a large file is needed, inspect the relevant region rather than the entire file when tooling permits.
- Ignore unrelated generated/vendor/cache directories.
- Do not inspect frontend when the confirmed issue is backend-only, and vice versa.
- Do not inspect infrastructure files for a pure business-logic change unless runtime behavior points there.

---

## Build and test budget

Use progressive verification:

```text
changed unit/function
-> affected module
-> affected service
-> integration
-> full regression/build
```

Stop at the earliest level that gives sufficient confidence for the task.

A full build/regression is justified for release/deployment or broad changes, but not as a ritual after every edit.

---

## Investigation-first tasks

If the user asks to:

- investigate;
- diagnose;
- find the cause;
- explain an error;

and does not explicitly ask for a fix, do **not** modify code.

Return the root cause, evidence, affected files, and proposed minimal fix.

This prevents unnecessary edits and repeated corrective work.

---

## User-requested implementation

If the user clearly asks to fix/implement something and the change is safe and sufficiently understood, do not waste resources asking for permission after producing a plan.

Proceed with the implementation.

Ask a question only when a missing business/technical decision cannot be safely derived from the repository or current instructions.

---

## Resource-efficiency anti-patterns

Avoid these patterns:

```text
"Let's inspect the whole repository first."
"Let's run all tests just to be safe."
"Let's rebuild all containers after every edit."
"Let's refactor this nearby code while we're here."
"Let's inspect every migration."
"Let's review all environment variables."
"Let's analyze all logs."
```

Replace them with the smallest targeted action that answers the current question.

---

## Completion discipline

Once all of the following are true:

- root cause or requested behavior is addressed;
- relevant targeted verification passed;
- no known directly related blocker remains;

stop using tools and report the result.

Do not continue searching for optional improvements unless the user asked for them.

---

# 2. Project architecture

High-level architecture:

```text
Browser
  |
  v
Frontend
  |
  v
Backend API
  |
  +---- PostgreSQL
  |
  +---- Redis
  |
  +---- Bitrix24 REST/OAuth
```

Production is Docker-based.

Expected repository layout:

```text
/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── migrations/
│   └── src/
│       └── cr_portal/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
└── docs/
```

Backend stack:

- Python;
- FastAPI;
- async SQLAlchemy;
- Alembic;
- PostgreSQL;
- Redis;
- httpx for external HTTP integrations.

Frontend is a separate web application.

Do not introduce a new framework, ORM, migration system, HTTP client, state-management system, or major dependency unless the task clearly requires it.

---

# 3. Core architectural rule: local Bitrix24 data

Bitrix24 is an external source of data.

Application modules should normally work from the **local synchronized database**, not make repeated Bitrix24 API requests for every screen/report/calculation.

Preferred flow:

```text
Bitrix24
   |
   v
Synchronization
   |
   v
Local PostgreSQL
   |
   +--> dashboards
   +--> reports
   +--> KPI
   +--> bonus calculations
```

Benefits of this architecture are intentional:

- fewer Bitrix24 API calls;
- reusable data across modules;
- faster reports;
- historical processing;
- predictable application behavior.

Do not bypass the local synchronization architecture unless there is a specific reason.

---

# 4. Bitrix24 integration rules

Bitrix24 integration is critical and should be changed conservatively.

The project already supports or has implemented infrastructure for:

- Bitrix24 OAuth installation;
- access tokens;
- refresh tokens;
- token expiration handling;
- portal/member installation data;
- users synchronization;
- deal funnels/categories;
- deals synchronization;
- background full synchronization;
- synchronization job status.

Known installation information includes concepts such as:

- `member_id`;
- `portal_domain`;
- `client_endpoint`;
- `access_token`;
- `refresh_token`;
- `expires_at`.

Relevant integration code is expected under:

```text
backend/src/cr_portal/integrations/bitrix/
```

and related API/service/model modules.

## Token handling

Never:

- hardcode an access token;
- hardcode a refresh token;
- expose tokens in logs;
- print secrets in diagnostic output;
- replace OAuth with a webhook without an explicit architectural decision;
- assume an expired token means the installation must be recreated.

When diagnosing authentication errors such as:

```text
401 Unauthorized
wrong_client
expired_token
```

inspect only the relevant flow first:

```text
installation record
    ->
client credentials/config
    ->
token refresh
    ->
stored refreshed tokens
    ->
actual Bitrix API request
```

Do not modify unrelated synchronization logic until the authentication path is confirmed.

## Bitrix fields and business semantics

Never invent:

- Bitrix field IDs;
- category IDs;
- stage IDs;
- user-field codes;
- business rules;
- mappings.

If a required Bitrix identifier is unknown, derive it from existing code/config/database/API response or ask for the missing business information.

---

# 5. Confirmed business-domain decisions

Treat these as current architectural/business rules unless newer code or explicit user instructions supersede them.

- The product is **CR Integration Portal**, not merely a bonus calculator.
- Calculations and analytics are built on locally synchronized Bitrix24 data.
- The key implementation employee is based on the project's **implementation responsible** concept, not blindly on Bitrix `assignedById`.
- `implementation_responsible_user_id` is an important normalized field.
- The dashboard uses the actual configured working funnels/categories.
- Do not hardcode historical deal counts.
- Deal activity should follow Bitrix stage semantics, not simplistic assumptions.
- Inactive Bitrix users may still be needed for historical mapping.
- Long synchronization operations should run as background jobs.
- Historical KPI should preserve result events/history where required.
- Business rules that can change over time should be versionable where practical.

Currently known working funnel names include:

- CR Start;
- Внедрение;
- Сопровождение;
- Тех интеграция.

Names/IDs in the live system remain the source of truth. Do not assume numeric category IDs from this document.

---

# 6. Database rules

PostgreSQL is the system's local source for synchronized and application-owned data.

## Before changing schema

Inspect:

1. the relevant SQLAlchemy model;
2. existing migrations touching that model/table;
3. related schemas/services;
4. queries that depend on the field.

Do not inspect every migration unless necessary.

## Schema changes

For persistent schema changes:

- create an Alembic migration;
- do not silently rely on ORM auto-creation;
- preserve existing data;
- avoid destructive migrations unless explicitly required;
- make migrations safe for production data;
- do not rewrite old applied migrations.

Before creating a new migration, check the current Alembic head.

Useful commands:

```bash
docker compose exec backend alembic heads
docker compose exec backend alembic current
```

Apply migrations with:

```bash
docker compose exec backend alembic upgrade head
```

Do not run destructive SQL against production-like data merely for debugging.

## Database diagnostics

Prefer focused queries.

Example principle:

```sql
SELECT id, member_id, portal_domain, expires_at
FROM bitrix_installations
LIMIT 10;
```

instead of:

```sql
SELECT * FROM every_large_table;
```

Never print secret token values unless explicitly necessary; mask them by default.

---

# 7. Backend rules

Backend source is under:

```text
backend/src/cr_portal/
```

Follow existing package boundaries and patterns.

Before creating a new module, search for an existing service/helper that already owns the responsibility.

Keep responsibilities separated where the existing codebase does so:

- API/router layer — HTTP concerns;
- schemas — request/response validation;
- services — application logic;
- models — persistence;
- integrations — external systems;
- jobs/background tasks — long-running work.

Avoid putting large business logic directly in FastAPI route handlers.

## Async code

The backend uses asynchronous infrastructure.

Do not introduce blocking network/database operations into async request paths.

Reuse async SQLAlchemy/httpx patterns already present in the repository.

---

# 8. Frontend rules

Frontend lives under:

```text
frontend/
```

Before changing UI:

1. locate the exact page/component;
2. inspect its API call/data types;
3. inspect shared components only if directly relevant.

Do not scan the whole frontend.

Prefer existing:

- component patterns;
- API client;
- types;
- layout;
- styling approach.

Do not replace working UI architecture or add a large UI library for a small task.

For backend contract changes, update frontend types/API usage only where necessary.

---

# 9. Docker and environments

The application is designed to run through Docker Compose.

Expected production services include:

- backend;
- frontend;
- postgres;
- redis.

Production should expose PostgreSQL and Redis only inside the Docker network.

Backend/frontend may be bound to localhost behind Nginx.

## Secrets

Secrets belong in environment files/environment variables and must not be committed.

Typical secret-bearing files include:

```text
.env
backend/.env
```

Never commit:

- passwords;
- OAuth client secrets;
- access tokens;
- refresh tokens;
- session secrets;
- private API credentials.

Do not replace `.env.example` values with real secrets.

---

# 10. Verification strategy

Use the cheapest validation that provides meaningful confidence.

## Level 1 — static/local targeted validation

For a small isolated change:

- syntax/type/lint check for the changed area if configured;
- targeted unit test;
- targeted frontend build/type check;
- import check.

Do not rebuild every Docker service automatically.

## Level 2 — affected service validation

When backend behavior changes, validate the backend and affected endpoint.

Useful health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

When relevant:

```bash
docker compose logs --tail=100 backend
```

Prefer:

```bash
docker compose logs --tail=100 backend
```

over dumping all logs.

## Level 3 — integration validation

Use Docker/DB/Bitrix integration validation only when the change affects those systems.

Examples:

```bash
docker compose ps
docker compose exec backend alembic current
```

## Level 4 — full rebuild/regression

Run a broader build/test only for:

- dependency changes;
- Dockerfile changes;
- compose changes;
- cross-cutting refactors;
- schema changes with broad impact;
- release/deployment preparation;
- when targeted checks cannot provide sufficient confidence.

Do not repeatedly run:

```bash
docker compose up -d --build
```

after every small source edit unless required.

---

# 11. Tests and project commands

Do not guess test/lint/build commands.

When needed, inspect the command definitions once from the smallest relevant configuration file:

Backend:

```text
backend/pyproject.toml
```

Frontend:

```text
frontend/package.json
```

Then reuse the discovered command during the task.

Prefer a single targeted test file/test case before the entire suite.

If no test currently covers modified critical logic, add a focused test when reasonable.

---

# 12. Debugging workflow

When fixing a bug:

1. reproduce or identify the exact failure;
2. search the exact error/symbol;
3. identify the narrow execution path;
4. find the root cause;
5. make the smallest safe fix;
6. validate the affected path;
7. stop.

Do not combine bug fixing with unrelated cleanup.

## Logs

Start with:

```bash
docker compose logs --tail=100 <service>
```

If necessary, filter:

```bash
docker compose logs <service> | grep -i '<relevant term>'
```

Increase scope only if the needed event is not present.

## Docker shell commands

Prefer simple POSIX-compatible commands inside containers.

Avoid unnecessarily complex nested shell quoting, especially from PowerShell to `docker compose exec ... sh -c`.

When masking environment secrets, prefer commands that are robust in the actual shell being used.

---

# 13. PowerShell awareness

Local development may be performed from Windows PowerShell.

Commands sent to the user should be compatible with the stated environment.

Do not assume Bash quoting rules when the command will be run from PowerShell.

If a command crosses:

```text
PowerShell -> docker compose exec -> sh
```

keep quoting as simple as possible.

---

# 14. Git rules

Default development branch has historically been:

```text
develop
```

Do not switch branches, reset, force-push, rebase shared history, or discard user changes unless explicitly asked.

Before changing a file that may contain user work, inspect relevant git status/diff if available.

Keep commits logically scoped.

Suggested commit style:

```text
Fix Bitrix token refresh
Add deal synchronization status
Add implementation responsible mapping
```

Do not commit generated artifacts, secrets, local caches, or environment files.

---

# 15. Production safety

Production deployment exists and changes must remain deployable.

Do not:

- alter Nginx/SSL/network exposure for an application-code bug;
- expose PostgreSQL or Redis publicly;
- delete Docker volumes casually;
- recreate the production database;
- run `docker system prune -a` as routine troubleshooting;
- remove migrations;
- overwrite production `.env`;
- make destructive database changes without explicit need.

For deployment-related work, inspect only the relevant infrastructure files.

Typical verification after deployment:

```bash
docker compose ps
curl http://127.0.0.1:8000/api/v1/health
curl -I http://127.0.0.1:3000
docker compose exec backend alembic current
```

---

# 16. Code-change policy

For every task, optimize for:

```text
correctness
    >
data safety
    >
compatibility with existing architecture
    >
small diff
    >
cleverness
```

Prefer:

- a 10-line fix in the correct layer

over:

- a 300-line refactor that happens to fix the same bug.

Do not rename/move files without a concrete reason.

Do not format unrelated files.

Do not upgrade dependencies opportunistically.

Do not change API response structures unless required.

Do not change database schema for a problem that can safely be solved without doing so.

---

# 17. Planning policy

For very small tasks, do not spend resources producing a large plan. Inspect and execute.

For medium or risky tasks, first provide a short plan of no more than roughly 3–6 steps.

A detailed plan is appropriate only for:

- large new features;
- schema redesign;
- major Bitrix synchronization changes;
- architecture changes;
- production deployment changes.

Do not repeatedly re-plan after each minor step.

---

# 18. Documentation hierarchy

When determining intended behavior, use this priority:

1. explicit instruction in the current task;
2. current working code and production behavior;
3. newest confirmed project specification;
4. recent project documentation;
5. older design discussions.

If old documentation conflicts with current implemented behavior, do not restore the old behavior merely because it is documented.

---

# 19. When information is missing

Do not invent technical or business facts.

If a safe implementation can proceed using existing patterns, proceed.

If a decision genuinely depends on missing business information, state exactly what is unknown.

Examples:

- unknown Bitrix user-field ID;
- unknown bonus percentage;
- unknown stage semantics;
- unknown responsible-employee business rule.

Avoid asking questions that can be answered by inspecting one obvious project file.

---

# 20. Definition of done

A task is done when:

- the requested behavior is implemented;
- unrelated code was not changed;
- relevant validation passed;
- schema migrations are included when required;
- secrets are not exposed;
- the final response identifies changed files and verification;
- remaining known limitations directly relevant to the task are stated.

Do not continue optimizing after the requested task is complete.

---

# 21. Compact operating rule

For every Codex task, internally follow:

```text
SEARCH NARROWLY
-> READ MINIMALLY
-> CHANGE LOCALLY
-> TEST TARGETED
-> REPORT CONCISELY
-> STOP
```

This rule is intentional: repository exploration, context growth, tool calls, full builds, and unnecessary test runs consume resources and should only be used when they materially improve correctness.
