$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Starting postgres + redis..."
docker compose up -d

$venvPy = ".\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "Creating venv..."
  python -m venv backend\.venv
  & $venvPy -m pip install -r backend\requirements.txt
}

$env:PYTHONPATH = (Resolve-Path .\backend).Path
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$pwd'; `$env:PYTHONPATH='$((Resolve-Path .\backend).Path)'; .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$pwd'; `$env:PYTHONPATH='$((Resolve-Path .\backend).Path)'; .\backend\.venv\Scripts\python.exe -m arq app.worker.WorkerSettings"
if (-not (Test-Path .\frontend\node_modules)) {
  Set-Location frontend
  npm install
  Set-Location ..
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$pwd\frontend'; npm run dev"

Write-Host "API  http://127.0.0.1:8000"
Write-Host "WEB  http://127.0.0.1:5173"
