Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$releaseRoot = Join-Path $repoRoot "release"
$packageRoot = Join-Path $releaseRoot "Team-Happy"
$zipPath = Join-Path $releaseRoot "Team-Happy-Windows-Portable.zip"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$InstallHint
    )
    if (!(Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name. $InstallHint"
    }
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

function Test-ZipEntry {
    param(
        [Parameter(Mandatory = $true)][object[]]$Entries,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $normalized = $Path.Replace("/", "\")
    return [bool]($Entries | Where-Object { $_.FullName.Replace("/", "\") -eq $normalized } | Select-Object -First 1)
}

Write-Step "Checking build tools"
Assert-Command "pnpm" "Install Node.js 20+ and enable pnpm with Corepack."
Assert-Command "uv" "Install uv first: https://docs.astral.sh/uv/getting-started/installation/"

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
Copy-RequiredFile (Join-Path $repoRoot ".env.example") (Join-Path $packageRoot ".env.example")
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

Write-Step "Removing generated caches"
Get-ChildItem -LiteralPath $packageRoot -Recurse -Force -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $packageRoot -Recurse -Force -File |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force

Write-Step "Checking for forbidden files"
$forbidden = @(
    ".git",
    ".venv",
    ".env",
    ".env.local",
    "frontend\node_modules",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    "*.pyc",
    "*.pyo",
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
$cacheLeftovers = @(
    Get-ChildItem -LiteralPath $packageRoot -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $packageRoot -Recurse -Force -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".pyc", ".pyo") }
)
if ($cacheLeftovers) {
    $sample = ($cacheLeftovers | Select-Object -First 5 | ForEach-Object { $_.FullName }) -join "; "
    throw "Forbidden Python cache files were copied into release package: $sample"
}

Write-Step "Creating zip package"
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal

Write-Step "Validating zip package"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entries = @($zip.Entries)
    $fileEntries = @($entries | Where-Object { $_.Length -gt 0 })
    if ($fileEntries.Count -lt 300) {
        throw "Zip package looks incomplete: only $($fileEntries.Count) file entries."
    }
    $requiredEntries = @(
        "Team-Happy\start-team-happy.bat",
        "Team-Happy\frontend\dist\index.html",
        "Team-Happy\server\app.py",
        "Team-Happy\lib\__init__.py",
        "Team-Happy\pyproject.toml",
        "Team-Happy\uv.lock",
        "Team-Happy\.env.example"
    )
    foreach ($entry in $requiredEntries) {
        if (!(Test-ZipEntry $entries $entry)) {
            throw "Zip package is missing required entry: $entry"
        }
    }
    $forbiddenZipEntries = @($entries | Where-Object {
        $name = $_.FullName.Replace("/", "\")
        $name -like "*\__pycache__\*" -or
        $name -like "*.pyc" -or
        $name -like "*.pyo" -or
        $name -like "Team-Happy\.env" -or
        $name -like "Team-Happy\.venv\*" -or
        $name -like "Team-Happy\frontend\node_modules\*" -or
        $name -like "Team-Happy\node_modules\*" -or
        $name -like "Team-Happy\projects\*" -or
        $name -like "Team-Happy\vertex_keys\*"
    })
    if ($forbiddenZipEntries) {
        $sample = ($forbiddenZipEntries | Select-Object -First 5 | ForEach-Object { $_.FullName }) -join "; "
        throw "Zip package contains forbidden entries: $sample"
    }
} finally {
    $zip.Dispose()
}

Write-Step "Portable package ready"
Write-Host "Release directory: $packageRoot"
Write-Host "Zip package:       $zipPath"
Write-Host "Start command:     double-click start-team-happy.bat"
Write-Host "LAN command:       double-click start-team-happy-lan.bat"
Write-Host "URL:               http://127.0.0.1:1242"
