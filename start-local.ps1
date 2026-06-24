# Digital Shadow — Local startup script (no Docker)
# Run from: C:\Users\Milana\Desktop\Simplex\digital-shadow
# Usage: .\start-local.ps1

$projectDir = $PSScriptRoot

Write-Host "=== Digital Shadow Local Start ===" -ForegroundColor Cyan

# 1. Redis
Write-Host "[1/5] Starting Redis..." -ForegroundColor Yellow
Start-Process -FilePath "C:\redis\redis-server.exe" `
    -ArgumentList "C:\redis\redis.windows.conf" `
    -WindowStyle Minimized

Start-Sleep -Seconds 2
$redisPing = & "C:\redis\redis-cli.exe" ping 2>&1
if ($redisPing -eq "PONG") {
    Write-Host "     Redis: OK" -ForegroundColor Green
} else {
    Write-Host "     Redis: FAILED - $redisPing" -ForegroundColor Red
}

# 2. Neo4j (already started as service or manually)
Write-Host "[2/5] Neo4j: start it manually if not running (see README)" -ForegroundColor Yellow

# 3. FastAPI
Write-Host "[3/5] Starting FastAPI (port 8000)..." -ForegroundColor Yellow
$env:PYTHONPATH = "$projectDir\backend;$projectDir"
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", `
    "cd '$projectDir'; `$env:PYTHONPATH='$projectDir\backend;$projectDir'; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" `
    -WorkingDirectory "$projectDir\backend"

Start-Sleep -Seconds 3

# 4. RQ Worker
Write-Host "[4/5] Starting RQ Worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", `
    "cd '$projectDir\backend'; `$env:PYTHONPATH='$projectDir\backend;$projectDir'; rq worker --url redis://localhost:6379/0 default"

# 5. Frontend
Write-Host "[5/5] Starting Frontend (port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", `
    "cd '$projectDir\frontend'; npm run dev"

Write-Host ""
Write-Host "=== All services started ===" -ForegroundColor Cyan
Write-Host "Frontend : http://localhost:5173" -ForegroundColor Green
Write-Host "API      : http://localhost:8000" -ForegroundColor Green
Write-Host "API docs : http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Next: run 'python scripts/seed.py' in a new terminal" -ForegroundColor Yellow
