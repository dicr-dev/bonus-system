param(
    [string]$Message = "Update project",
    [string]$Month = "2026-08",
    [string]$Server = "root@vm4579464",
    [string]$ProjectPath = "/opt/cr-portal"
)

$ErrorActionPreference = "Stop"

$RepoPath = "C:\Users\cruser\Documents\GitHub\bonus-system-prod"
$BackendPath = Join-Path $RepoPath "backend"

function Run-Step {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "========================================"
    Write-Host $Title
    Write-Host "========================================"

    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "Ошибка на этапе: $Title"
    }
}

Run-Step "1. Проверка Python" {
    Set-Location $BackendPath
    uv run python -m compileall -q src
}

Run-Step "2. Запуск тестов" {
    Set-Location $BackendPath
    uv run pytest
}

Run-Step "3. Git add" {
    Set-Location $RepoPath
    git add .
}

Set-Location $RepoPath

$changes = git status --porcelain

if ($changes) {
    Run-Step "4. Git commit" {
        git commit -m $Message
    }

    Run-Step "5. Git push" {
        git push origin develop
    }
}
else {
    Write-Host ""
    Write-Host "Изменений для commit нет. Push пропускаем."
}

$RemoteScript = @"
set -e

cd $ProjectPath

echo
echo "========================================"
echo "Git pull"
echo "========================================"
git pull origin develop

echo
echo "========================================"
echo "Docker build / restart"
echo "========================================"
docker compose up -d --build backend worker

echo
echo "========================================"
echo "Docker status"
echo "========================================"
docker compose ps

echo
echo "========================================"
echo "Diagnostics $Month"
echo "========================================"
curl -s -X POST "https://integration.crmicro.ru/api/v1/diagnostics/run?month=$Month"

echo
echo
echo "========================================"
echo "Diagnostics summary"
echo "========================================"

docker compose exec -T postgres psql \
    -P pager=off \
    -U cr_portal \
    -d cr_portal \
    -c "
SELECT
    severity,
    code,
    COUNT(*) AS count
FROM calculation_issues
WHERE month = DATE '${Month}-01'
  AND calculation_id IS NULL
GROUP BY severity, code
ORDER BY severity, code;
"
"@

Run-Step "6. Обновление сервера" {
    $RemoteScript | ssh $Server "bash -s"
}

Write-Host ""
Write-Host "========================================"
Write-Host "DEPLOY ЗАВЕРШЕН"
Write-Host "========================================"