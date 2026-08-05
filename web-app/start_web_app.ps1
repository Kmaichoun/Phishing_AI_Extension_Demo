param(
  [int]$Port = 5505
)

$ErrorActionPreference = "Stop"
$WebDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $WebDir

if ($Port -ne 5505) {
  Write-Warning "Backend must set AUTH_WEB_ORIGINS for web port $Port before Login will work."
}

Write-Host "Starting Phish Radar AI Web App..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath (Join-Path $WebDir 'node_modules'))) {
  throw "React dependencies not found. Run 'npm install' inside web-app first."
}

Write-Host "URL: http://app.phishradar.localhost:$Port/#/login" -ForegroundColor Green
Write-Host "Press CTRL+C to stop this web server." -ForegroundColor Yellow
Start-Process "http://app.phishradar.localhost:$Port/#/login"
npm run dev -- --port $Port
