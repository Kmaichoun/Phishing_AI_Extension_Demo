[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$setupScript = Join-Path $PSScriptRoot 'setup_local_domain.ps1'
$fixturePath = Join-Path ([IO.Path]::GetTempPath()) "phish-radar-hosts-$([guid]::NewGuid().ToString('N')).txt"
$baseline = @(
  '# local test fixture',
  '127.0.0.1 localhost'
)

try {
  Set-Content -LiteralPath $fixturePath -Value $baseline -Encoding ascii

  & $setupScript -HostsPath $fixturePath
  & $setupScript -HostsPath $fixturePath
  $configured = @(Get-Content -LiteralPath $fixturePath)

  if (@($configured | Where-Object { $_ -match 'app\.phishradar\.localhost' }).Count -ne 1) {
    throw 'Web App domain was not added exactly once.'
  }
  if (@($configured | Where-Object { $_ -match 'api\.phishradar\.localhost' }).Count -ne 1) {
    throw 'API domain was not added exactly once.'
  }

  & $setupScript -HostsPath $fixturePath -Remove
  $removed = @(Get-Content -LiteralPath $fixturePath)
  if (($removed -join "`n") -ne ($baseline -join "`n")) {
    throw 'Removing the managed domain block did not restore the fixture.'
  }

  Write-Host 'Local domain setup test passed.' -ForegroundColor Green
} finally {
  if (Test-Path -LiteralPath $fixturePath) {
    Remove-Item -LiteralPath $fixturePath -Force
  }
}
