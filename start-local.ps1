<#
Starts Faceless Forge locally from the repository root.

Usage:
  .\start-local.ps1

The first run creates .venv and installs the production dependencies.  It also
creates backend\.env from .env.example when necessary, then stops so secrets
can be filled in safely before the server starts.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$envFile = Join-Path $backendDir '.env'
$envTemplate = Join-Path $projectRoot '.env.example'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Creating local Python virtual environment...'
    python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Không thể tạo Python virtual environment.' }
}

Write-Host 'Installing/updating Faceless Forge dependencies...'
& $venvPython -m pip install -r (Join-Path $backendDir 'requirements.production.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'Cài dependency thất bại. Kiểm tra kết nối mạng hoặc thông báo pip ở trên.'
}

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envTemplate -Destination $envFile
    Write-Warning "Created $envFile. Add your real EMERGENT_LLM_KEY and MONGO_URL, then run this command again."
    exit 1
}

Write-Host "Starting Faceless Forge at http://127.0.0.1:$Port"
Push-Location $backendDir
try {
    & $venvPython -m uvicorn forge_premium_app:app --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
