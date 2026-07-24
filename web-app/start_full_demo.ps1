param(
  [int]$WebPort = 5505,
  [int]$BackendPort = 8765
)

$ErrorActionPreference = "Stop"
$WebDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $WebDir
$BackendDir = Join-Path $ProjectDir "backend"
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $BackendDir)) {
  throw "Backend folder not found: $BackendDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $BackendDir "app.py"))) {
  throw "Backend app.py not found in: $BackendDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $WebDir "server.js"))) {
  throw "Web server.js not found in: $WebDir"
}

$PythonCommand = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$backendCommand = "`$env:PYTHONDONTWRITEBYTECODE='1'; `$env:AUTH_WEB_ORIGINS='http://app.phishradar.localhost:$WebPort,http://127.0.0.1:$WebPort,http://localhost:$WebPort'; & `"$PythonCommand`" -m uvicorn app:app --host 127.0.0.1 --port $BackendPort --reload"
$webCommand = "`$env:PORT='$WebPort'; node .\server.js"

Write-Host "Opening backend from:" -ForegroundColor Cyan
Write-Host $BackendDir
Start-Process -FilePath "powershell" -WorkingDirectory $BackendDir -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $backendCommand)

Start-Sleep -Seconds 2

Write-Host "Opening web app from:" -ForegroundColor Cyan
Write-Host $WebDir
Start-Process -FilePath "powershell" -WorkingDirectory $WebDir -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $webCommand)

Start-Sleep -Seconds 1
Start-Process "http://app.phishradar.localhost:$WebPort/login.html"

Write-Host "Started backend at http://127.0.0.1:$BackendPort" -ForegroundColor Green
Write-Host "Started web app at http://app.phishradar.localhost:$WebPort" -ForegroundColor Green
