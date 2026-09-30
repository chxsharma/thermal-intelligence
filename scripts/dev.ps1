$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "cd '$root\backend'; if (Test-Path .venv\Scripts\Activate.ps1) { . .venv\Scripts\Activate.ps1 }; uvicorn app.main:app --port 8000"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "cd '$root\frontend'; if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { npm.cmd run dev } else { npm run dev }"
Write-Host "Backend http://localhost:8000  Frontend http://localhost:3000"
