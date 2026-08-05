[CmdletBinding(SupportsShouldProcess)]
param(
  [switch]$IncludeVenv,
  [switch]$IncludeNodeModules
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$ProjectPrefix = $ProjectRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar

function Get-DirectorySize {
  param([Parameter(Mandatory)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    return [int64]0
  }

  $measurement = Get-ChildItem -LiteralPath $Path -Recurse -File -Force `
    -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
  if ($null -eq $measurement.Sum) {
    return [int64]0
  }
  return [int64]$measurement.Sum
}

function Assert-ProjectPath {
  param([Parameter(Mandatory)][string]$Path)

  $fullPath = [System.IO.Path]::GetFullPath($Path)
  if (-not $fullPath.StartsWith(
      $ProjectPrefix,
      [System.StringComparison]::OrdinalIgnoreCase
    )) {
    throw "Refusing to clean a path outside the project: $fullPath"
  }
  return $fullPath
}

function Remove-ProjectItem {
  param([Parameter(Mandatory)][string]$Path)

  $safePath = Assert-ProjectPath $Path
  if (-not (Test-Path -LiteralPath $safePath)) {
    return
  }

  if ($PSCmdlet.ShouldProcess($safePath, 'Remove generated project artifact')) {
    Remove-Item -LiteralPath $safePath -Recurse -Force
    Write-Host "Removed: $($safePath.Substring($ProjectPrefix.Length))"
  }
}

$beforeBytes = Get-DirectorySize $ProjectRoot
$cleanupTargets = [System.Collections.Generic.List[string]]::new()
$cleanupTargets.Add((Join-Path $ProjectRoot 'tmp'))
$cleanupTargets.Add((Join-Path $ProjectRoot 'web-app/dist'))

foreach ($cacheDirectoryName in @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')) {
  Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Directory `
    -Filter $cacheDirectoryName -Force -ErrorAction SilentlyContinue |
    Where-Object {
      -not $_.FullName.StartsWith(
        (Join-Path $ProjectRoot '.venv'),
        [System.StringComparison]::OrdinalIgnoreCase
      )
    } |
    ForEach-Object { $cleanupTargets.Add($_.FullName) }
}

$outputDirectory = Join-Path $ProjectRoot 'output'
if (Test-Path -LiteralPath $outputDirectory -PathType Container) {
  Get-ChildItem -LiteralPath $outputDirectory -Recurse -File `
    -Filter '*.inspect.ndjson' -Force -ErrorAction SilentlyContinue |
    ForEach-Object { $cleanupTargets.Add($_.FullName) }
}

if ($IncludeVenv) {
  $cleanupTargets.Add((Join-Path $ProjectRoot '.venv'))
}
if ($IncludeNodeModules) {
  $cleanupTargets.Add((Join-Path $ProjectRoot 'web-app/node_modules'))
}

$cleanupTargets |
  Sort-Object -Unique |
  Sort-Object { $_.Length } -Descending |
  ForEach-Object { Remove-ProjectItem $_ }

$afterBytes = Get-DirectorySize $ProjectRoot
$savedBytes = [Math]::Max(0, $beforeBytes - $afterBytes)

Write-Host ''
Write-Host ('Before: {0:N2} MB' -f ($beforeBytes / 1MB))
Write-Host ('After:  {0:N2} MB' -f ($afterBytes / 1MB))
Write-Host ('Saved:  {0:N2} MB' -f ($savedBytes / 1MB)) -ForegroundColor Green

if ($IncludeVenv) {
  Write-Warning 'The virtual environment was removed. Recreate it and install backend/requirements.txt before starting the Backend.'
}
if ($IncludeNodeModules) {
  Write-Warning 'React dependencies were removed. Run npm install inside web-app before starting the Web App.'
}
