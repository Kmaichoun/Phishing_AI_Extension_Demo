[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$validationErrors = [System.Collections.Generic.List[string]]::new()

function Add-ValidationError {
  param([Parameter(Mandatory)][string]$Message)
  $validationErrors.Add($Message) | Out-Null
}

function Test-ProjectFile {
  param([Parameter(Mandatory)][string]$RelativePath)

  $normalizedPath = $RelativePath.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
  $fullPath = Join-Path $ProjectRoot $normalizedPath
  if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
    Add-ValidationError "Missing file: $RelativePath"
  }
}

function Get-ProjectRelativePath {
  param([Parameter(Mandatory)][string]$FullPath)

  $rootWithSeparator = $ProjectRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($FullPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $FullPath.Substring($rootWithSeparator.Length)
  }
  return $FullPath
}

Push-Location $ProjectRoot
try {
  Write-Host '1/6 Validating JSON files...' -ForegroundColor Cyan
  $manifest = $null
  try {
    $manifest = Get-Content -Raw -LiteralPath 'manifest.json' | ConvertFrom-Json
    Get-Content -Raw -LiteralPath 'web-app/manifest.webmanifest' | ConvertFrom-Json | Out-Null
  } catch {
    Add-ValidationError "Invalid JSON: $($_.Exception.Message)"
  }

  Write-Host '2/6 Validating extension manifest resources...' -ForegroundColor Cyan
  if ($null -ne $manifest) {
    $manifestResources = [System.Collections.Generic.List[string]]::new()
    $manifestResources.Add([string]$manifest.background.service_worker)
    $manifestResources.Add([string]$manifest.action.default_popup)

    foreach ($icon in $manifest.icons.PSObject.Properties) {
      $manifestResources.Add([string]$icon.Value)
    }
    foreach ($contentScript in $manifest.content_scripts) {
      foreach ($resource in @($contentScript.js) + @($contentScript.css)) {
        $manifestResources.Add([string]$resource)
      }
    }
    foreach ($resourceGroup in $manifest.web_accessible_resources) {
      foreach ($resource in $resourceGroup.resources) {
        $manifestResources.Add([string]$resource)
      }
    }

    foreach ($resource in $manifestResources | Sort-Object -Unique) {
      if (-not [string]::IsNullOrWhiteSpace($resource)) {
        Test-ProjectFile $resource
      }
    }
  }

  Write-Host '3/6 Validating local HTML resources...' -ForegroundColor Cyan
  $htmlFiles = @(
    Get-ChildItem -LiteralPath $ProjectRoot -File -Filter '*.html'
    Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'web-app') -File -Filter '*.html'
  )
  foreach ($htmlFile in $htmlFiles) {
    $html = Get-Content -Raw -LiteralPath $htmlFile.FullName
    foreach ($match in [regex]::Matches($html, '(?:src|href)="([^"]+)"')) {
      $resource = $match.Groups[1].Value
      if ($resource -match '^(?:[a-z]+:|//|#)' -or [string]::IsNullOrWhiteSpace($resource)) {
        continue
      }

      $resourceWithoutQuery = ($resource -split '[?#]', 2)[0]
      $resourcePath = Join-Path $htmlFile.DirectoryName $resourceWithoutQuery
      if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) {
        $relativeHtml = Get-ProjectRelativePath $htmlFile.FullName
        Add-ValidationError "Missing HTML resource '$resource' referenced by '$relativeHtml'"
      }
    }
  }

  Write-Host '4/6 Checking required project files...' -ForegroundColor Cyan
  $requiredFiles = @(
    'DESIGN.md',
    'app-trust.js',
    'dockit-extension.css',
    'extension-theme.js',
    'extension-motion.js',
    'backend/app.py',
    'backend/auth_models.py',
    'backend/auth_router.py',
    'backend/database.py',
    'backend/feature_extractor.py',
    'backend/llm_explainer.py',
    'backend/requirements.txt',
    'backend/data/seed_urls.csv',
    'database/mysql/README_TH.md',
    'database/mysql/create_database.sql',
    'database/mysql/migrations/001_create_users.sql',
    'database/mysql/migrations/002_create_user_devices.sql',
    'database/mysql/migrations/003_create_sessions.sql',
    'database/mysql/migrations/004_create_search_history.sql',
    'scripts/test_auth_flow.py',
    'scripts/test_mysql_contract.py',
    'scripts/test_domain_cors.py',
    'scripts/test_app_trust.js',
    'scripts/test_popup_ui.js',
    'scripts/test_web_app_ui.js',
    'scripts/setup_local_domain.ps1',
    'scripts/test_local_domain_setup.ps1',
    'web-app/package.json',
    'web-app/package-lock.json',
    'web-app/vite.config.mjs',
    'web-app/auth.css',
    'web-app/dockit-theme.css',
    'web-app/fonts.css',
    'web-app/professional-ui.css',
    'web-app/index.html',
    'web-app/styles.css',
    'web-app/analyzer.js',
    'web-app/manifest.webmanifest',
    'web-app/src/main.jsx',
    'web-app/src/App.jsx',
    'web-app/src/react.css',
    'web-app/src/components/AppHeader.jsx',
    'web-app/src/components/MotionFrame.jsx',
    'web-app/src/components/ProtectedRoute.jsx',
    'web-app/src/contexts/AuthContext.jsx',
    'web-app/src/contexts/AppContext.jsx',
    'web-app/src/contexts/RouterContext.jsx',
    'web-app/src/contexts/ThemeContext.jsx',
    'web-app/src/pages/LoginPage.jsx',
    'web-app/src/pages/ScannerPage.jsx',
    'web-app/src/pages/QrPage.jsx',
    'web-app/src/pages/DashboardPage.jsx',
    'web-app/src/pages/SettingsPage.jsx',
    'web-app/src/services/api.js',
    'web-app/src/services/risk.js',
    'web-app/src/services/runtime.js',
    'web-app/assets/brand-mark.svg',
    'web-app/assets/icon128.png',
    'web-app/assets/fonts/outfit-latin-400-700.woff2',
    'web-app/assets/fonts/ibm-plex-sans-thai-400.woff2',
    'web-app/assets/fonts/ibm-plex-sans-thai-500.woff2',
    'web-app/assets/fonts/ibm-plex-sans-thai-600.woff2',
    'web-app/assets/fonts/ibm-plex-sans-thai-700.woff2',
    'web-app/assets/fonts/noto-serif-thai-500-600.woff2'
  )
  foreach ($requiredFile in $requiredFiles) {
    Test-ProjectFile $requiredFile
  }

  $authSchemaPath = Join-Path $ProjectRoot 'database/mysql/migrations/001_create_users.sql'
  if (Test-Path -LiteralPath $authSchemaPath -PathType Leaf) {
    $authSchema = Get-Content -Raw -LiteralPath $authSchemaPath
    $requiredSchemaFragments = @(
      'CREATE TABLE IF NOT EXISTS `Users`',
      '`PasswordHash` VARCHAR(255) NOT NULL',
      '`Role` ENUM(''user'', ''admin'')',
      'UNIQUE (`NormalizedUsername`)',
      'UNIQUE (`NormalizedEmail`)'
    )
    foreach ($requiredSchemaFragment in $requiredSchemaFragments) {
      if (-not $authSchema.Contains($requiredSchemaFragment)) {
        Add-ValidationError "Authentication schema is missing: $requiredSchemaFragment"
      }
    }
    if ($authSchema -match '(?im)^\s*`Password`\s+') {
      Add-ValidationError 'Authentication schema must not contain a plaintext Password column.'
    }
  }

  Write-Host '5/6 Checking JavaScript and Python syntax...' -ForegroundColor Cyan
  $node = Get-Command node -ErrorAction SilentlyContinue
  if ($null -eq $node) {
    Add-ValidationError 'Node.js was not found; JavaScript syntax could not be checked.'
  } else {
    $javascriptFiles = @(
      Get-ChildItem -LiteralPath $ProjectRoot -File -Filter '*.js'
      Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'web-app') -File -Filter '*.js'
      Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter '*.js'
    )
    foreach ($javascriptFile in $javascriptFiles) {
      & $node.Source --check $javascriptFile.FullName
      if ($LASTEXITCODE -ne 0) {
        Add-ValidationError "JavaScript syntax failed: $($javascriptFile.FullName)"
      }
    }

    & $node.Source (Join-Path $PSScriptRoot 'smoke_test_analyzers.js')
    if ($LASTEXITCODE -ne 0) {
      Add-ValidationError 'Analyzer smoke tests failed.'
    }

    & $node.Source (Join-Path $PSScriptRoot 'test_app_trust.js')
    if ($LASTEXITCODE -ne 0) {
      Add-ValidationError 'Trusted Web App origin tests failed.'
    }

    & $node.Source (Join-Path $PSScriptRoot 'test_popup_ui.js')
    if ($LASTEXITCODE -ne 0) {
      Add-ValidationError 'Popup UI contract tests failed.'
    }

    & $node.Source (Join-Path $PSScriptRoot 'test_web_app_ui.js')
    if ($LASTEXITCODE -ne 0) {
      Add-ValidationError 'Web App professional UI contract tests failed.'
    }
  }

  $venvPythonPath = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  $pythonPath = if (Test-Path -LiteralPath $venvPythonPath -PathType Leaf) {
    $venvPythonPath
  } elseif ($null -ne $pythonCommand) {
    $pythonCommand.Source
  } else {
    $null
  }

  if ($null -eq $pythonPath) {
    Write-Warning 'Python was not found; backend syntax was skipped.'
  } else {
    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    $env:PYTHONDONTWRITEBYTECODE = '1'
    try {
      & $pythonPath -c "import ast, pathlib; files=list(pathlib.Path('backend').glob('*.py')); [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]"
      if ($LASTEXITCODE -ne 0) {
        Add-ValidationError 'Python syntax check failed.'
      }

      & $pythonPath (Join-Path $PSScriptRoot 'test_domain_cors.py')
      if ($LASTEXITCODE -ne 0) {
        Add-ValidationError 'Custom Web App domain CORS test failed.'
      }

      & $pythonPath (Join-Path $PSScriptRoot 'test_mysql_contract.py')
      if ($LASTEXITCODE -ne 0) {
        Add-ValidationError 'MySQL schema and Backend contract test failed.'
      }
    } finally {
      $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
  }

  Write-Host '6/6 Checking generated and backup artifacts...' -ForegroundColor Cyan
  $backupArtifacts = @(
    Get-ChildItem -LiteralPath $ProjectRoot -Directory -Filter 'backup-*'
    Get-ChildItem -LiteralPath $ProjectRoot -File -Filter '*.backup-*'
  )
  foreach ($backupArtifact in $backupArtifacts) {
    Add-ValidationError "Backup artifact should not be in project root: $($backupArtifact.Name)"
  }

  $pythonCaches = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Directory -Filter '__pycache__' |
    Where-Object { $_.FullName -notlike "$(Join-Path $ProjectRoot '.venv')*" }
  foreach ($pythonCache in $pythonCaches) {
    $relativeCache = Get-ProjectRelativePath $pythonCache.FullName
    Add-ValidationError "Python cache should be removed: $relativeCache"
  }

  $inspectionArtifacts = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'output') `
    -Recurse -File -Filter '*.inspect.ndjson' -ErrorAction SilentlyContinue
  foreach ($inspectionArtifact in $inspectionArtifacts) {
    $relativeArtifact = Get-ProjectRelativePath $inspectionArtifact.FullName
    Add-ValidationError "Generated inspection artifact should be removed: $relativeArtifact"
  }

  if ($validationErrors.Count -gt 0) {
    Write-Host ''
    foreach ($validationError in $validationErrors) {
      Write-Host "ERROR: $validationError" -ForegroundColor Red
    }
    throw "Project validation failed with $($validationErrors.Count) error(s)."
  }

  Write-Host ''
  Write-Host 'Project validation passed.' -ForegroundColor Green
} finally {
  Pop-Location
}
