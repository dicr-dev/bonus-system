param(
    [string]$Message = "Update project",
    [string]$Month = "2026-08",
    [string]$Server = "root@45.90.217.67",
    [string]$ProjectPath = "/opt/cr-portal"
)

$ErrorActionPreference = "Stop"
$RepoPath = "C:\Users\cruser\Documents\GitHub\bonus-system-prod"
$BackendPath = Join-Path $RepoPath "backend"

function Run-Step {
    param([string]$Title,[scriptblock]$Command)
    Write-Host ""
    Write-Host "========================================"
    Write-Host $Title
    Write-Host "========================================"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Failed step: $Title" }
}

Run-Step "1. Python compile check" {
    Set-Location $BackendPath
    uv run python -m compileall -q src migrations
}

Run-Step "2. Backend tests" {
    Set-Location $BackendPath
    uv run pytest
}

Run-Step "3. Frontend build" {
    Set-Location (Join-Path $RepoPath "frontend")
    npm run build
}

Run-Step "4. Git add" {
    Set-Location $RepoPath
    git add .
}

Set-Location $RepoPath
$changes = git status --porcelain
if ($changes) {
    Run-Step "5. Git commit" { git commit -m $Message }
    Run-Step "6. Git push" { git push origin develop }
} else {
    Write-Host "No local changes. Commit and push skipped."
}

$RemoteScript = @"
set -euo pipefail
cd "$ProjectPath"

echo "=== Git pull ==="
git pull origin develop

echo "=== Build images ==="
docker compose build backend worker frontend

echo "=== Database migrations ==="
docker compose run --rm backend alembic upgrade head

echo "=== Restart services ==="
docker compose up -d backend worker frontend

echo "=== Containers ==="
docker compose ps

echo "=== Diagnostics $Month ==="
curl -fsS -X POST "https://integration.crmicro.ru/api/v1/diagnostics/run?month=$Month" > /tmp/cr_diagnostics.json
python3 - <<'PY'
import json
with open('/tmp/cr_diagnostics.json', encoding='utf-8') as f:
    data = json.load(f)
print('Diagnostics returned:', len(data), 'issues')
PY

echo "=== Diagnostics summary ==="
docker compose exec -T postgres psql -P pager=off -U cr_portal -d cr_portal -c "SELECT severity, code, COUNT(*) AS count FROM calculation_issues WHERE month = DATE '${Month}-01' AND calculation_id IS NULL GROUP BY severity, code ORDER BY severity, code;"
"@

Run-Step "7. Server deploy" {
    $RemoteScript | ssh $Server "bash -s"
}

Write-Host ""
Write-Host "========================================"
Write-Host "DEPLOY COMPLETED"
Write-Host "========================================"
