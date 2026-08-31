# Bonus details UI update

Обновление делает следующее:

- В списке расчетов показывает ФИО вместо UUID сотрудника.
- В детализации показывает название сделки и Bitrix ID.
- Делит детализацию на разделы.
- Показывает итог по каждому разделу.
- Для "Текущий клиент" показывает базу в машинах, а не в рублях.
- Для часов показывает количество часов и ставку в руб./ч.
- Если `support_hours` отсутствует в расчете, интерфейс явно показывает предупреждение.

## Установка локально (PowerShell)

Распакуйте ZIP поверх корня репозитория:

C:\Users\cruser\Documents\GitHub\bonus-system-prod

После распаковки запустите:

```powershell
.\apply_bonus_details_update.ps1
```

Проверка backend:

```powershell
cd .\backend
python -m compileall src
cd ..
```

Проверка frontend:

```powershell
cd .\frontend
npm ci
npm run build
cd ..
```

Git:

```powershell
git status
git add backend/src/cr_portal/api/v1/calculations.py backend/src/cr_portal/schemas/bonus.py frontend/src/types.ts frontend/src/App.tsx
git commit -m "Improve bonus calculation details UI"
git push origin develop
```

## Продакшен

```powershell
ssh root@45.90.217.67 "cd /opt/cr-portal && git pull origin develop && docker compose build backend frontend && docker compose up -d --force-recreate backend frontend"
```

Миграция БД для этого обновления не требуется.
