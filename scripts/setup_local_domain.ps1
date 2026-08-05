[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$WebDomain = 'app.phishradar.localhost',
  [string]$ApiDomain = 'api.phishradar.localhost',
  [string]$HostsPath = "$env:SystemRoot\System32\drivers\etc\hosts",
  [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($domain in @($WebDomain, $ApiDomain)) {
  if ($domain -notmatch '^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$') {
    throw "Invalid local domain: $domain"
  }
}

$systemHosts = [System.IO.Path]::GetFullPath("$env:SystemRoot\System32\drivers\etc\hosts")
$resolvedHosts = [System.IO.Path]::GetFullPath($HostsPath)
if ($resolvedHosts -eq $systemHosts) {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  $isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if (-not $isAdministrator) {
    throw 'กรุณาเปิด PowerShell แบบ Run as administrator แล้วรันสคริปต์นี้อีกครั้ง'
  }
}

if (-not (Test-Path -LiteralPath $resolvedHosts -PathType Leaf)) {
  throw "Hosts file not found: $resolvedHosts"
}

$beginMarker = '# BEGIN PHISH RADAR AI LOCAL DOMAINS'
$endMarker = '# END PHISH RADAR AI LOCAL DOMAINS'
$lines = @(Get-Content -LiteralPath $resolvedHosts)
$filtered = [System.Collections.Generic.List[string]]::new()
$insideManagedBlock = $false

foreach ($line in $lines) {
  if ($line.Trim() -eq $beginMarker) {
    $insideManagedBlock = $true
    continue
  }
  if ($insideManagedBlock -and $line.Trim() -eq $endMarker) {
    $insideManagedBlock = $false
    continue
  }
  if (-not $insideManagedBlock) {
    $filtered.Add($line)
  }
}

while ($filtered.Count -gt 0 -and [string]::IsNullOrWhiteSpace($filtered[$filtered.Count - 1])) {
  $filtered.RemoveAt($filtered.Count - 1)
}

if (-not $Remove) {
  if ($filtered.Count -gt 0) { $filtered.Add('') }
  $filtered.Add($beginMarker)
  $filtered.Add("127.0.0.1`t$WebDomain")
  $filtered.Add("127.0.0.1`t$ApiDomain")
  $filtered.Add($endMarker)
}

$action = if ($Remove) { 'Remove Phish Radar local domains from' } else { 'Add Phish Radar local domains to' }
if ($PSCmdlet.ShouldProcess($resolvedHosts, $action)) {
  if ($resolvedHosts -eq $systemHosts) {
    $backupPath = "$resolvedHosts.phish-radar.bak"
    if (-not (Test-Path -LiteralPath $backupPath)) {
      Copy-Item -LiteralPath $resolvedHosts -Destination $backupPath
    }
  }
  Set-Content -LiteralPath $resolvedHosts -Value $filtered -Encoding ascii
  if ($resolvedHosts -eq $systemHosts) {
    try { Clear-DnsClientCache -ErrorAction Stop } catch { Write-Warning "Could not clear DNS cache: $($_.Exception.Message)" }
  }
}

if ($Remove) {
  Write-Host 'Removed Phish Radar local domains.' -ForegroundColor Yellow
} else {
  Write-Host "Web App: http://$WebDomain`:5505/#/login" -ForegroundColor Green
  Write-Host "Backend: http://$ApiDomain`:8765/health" -ForegroundColor Green
}
