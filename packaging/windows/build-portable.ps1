Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$releaseRoot = Join-Path $repoRoot "release"
$packageRoot = Join-Path $releaseRoot "Team-Happy"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Copy-DirectoryClean {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    if (!(Test-Path $Source)) {
        throw "Missing required directory: $Source"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -Path $Source -Destination $Destination -Recurse -Force
}

function Copy-RequiredFile {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    if (!(Test-Path $Source)) {
        throw "Missing required file: $Source"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -Path $Source -Destination $Destination -Force
}

Write-Step "Building frontend"
Push-Location (Join-Path $repoRoot "frontend")
try {
    pnpm build
} finally {
    Pop-Location
}

Write-Step "Cleaning release directory"
if (Test-Path $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

Write-Step "Copying runtime files"
Copy-DirectoryClean (Join-Path $repoRoot "server") (Join-Path $packageRoot "server")
Copy-DirectoryClean (Join-Path $repoRoot "lib") (Join-Path $packageRoot "lib")
Copy-DirectoryClean (Join-Path $repoRoot "agent_runtime_profile") (Join-Path $packageRoot "agent_runtime_profile")
Copy-DirectoryClean (Join-Path $repoRoot "alembic") (Join-Path $packageRoot "alembic")
Copy-DirectoryClean (Join-Path $repoRoot "scripts") (Join-Path $packageRoot "scripts")

New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "frontend") | Out-Null
Copy-DirectoryClean (Join-Path $repoRoot "frontend\dist") (Join-Path $packageRoot "frontend\dist")

Copy-RequiredFile (Join-Path $repoRoot "pyproject.toml") (Join-Path $packageRoot "pyproject.toml")
Copy-RequiredFile (Join-Path $repoRoot "uv.lock") (Join-Path $packageRoot "uv.lock")
Copy-RequiredFile (Join-Path $repoRoot "README.md") (Join-Path $packageRoot "README.md")
Copy-RequiredFile (Join-Path $repoRoot "alembic.ini") (Join-Path $packageRoot "alembic.ini")
Copy-RequiredFile (Join-Path $repoRoot "skills-lock.json") (Join-Path $packageRoot "skills-lock.json")
Copy-RequiredFile (Join-Path $repoRoot "CLAUDE.md") (Join-Path $packageRoot "CLAUDE.md")
Copy-RequiredFile (Join-Path $scriptDir "start-team-happy.bat") (Join-Path $packageRoot "start-team-happy.bat")
Copy-RequiredFile (Join-Path $scriptDir "start-team-happy-lan.bat") (Join-Path $packageRoot "start-team-happy-lan.bat")
Copy-RequiredFile (Join-Path $scriptDir "README-Windows-Portable.md") (Join-Path $packageRoot "README-Windows-Portable.md")
Copy-RequiredFile (Join-Path $scriptDir "README-Windows-LAN.md") (Join-Path $packageRoot "README-Windows-LAN.md")

Write-Step "Creating writable data directory"
New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "data") | Out-Null

Write-Step "Checking for forbidden files"
$forbidden = @(
    ".git",
    ".venv",
    ".env",
    ".env.local",
    "frontend\node_modules",
    "node_modules",
    ".pytest_cache",
    "logs",
    "projects",
    "vertex_keys"
)
foreach ($relative in $forbidden) {
    $candidate = Join-Path $packageRoot $relative
    if (Test-Path $candidate) {
        throw "Forbidden path was copied into release package: $relative"
    }
}

Write-Step "Portable package ready"
Write-Host "Release directory: $packageRoot"
Write-Host "Start command:     double-click start-team-happy.bat"
Write-Host "LAN command:       double-click start-team-happy-lan.bat"
Write-Host "URL:               http://127.0.0.1:1241"
