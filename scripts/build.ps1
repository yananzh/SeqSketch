<#
.SYNOPSIS
    Build BioSeqAnalyzer.exe (single-file, no console, Windows GUI).

.DESCRIPTION
    Uses PyInstaller.  No C compiler required.
    Produces: dist\BioSeqAnalyzer.exe

    softwares/ is intentionally excluded – place BLAST+, MUSCLE, IQ-TREE, trimAl
    anywhere on your machine and configure their paths inside the application.

.PARAMETER PythonExe
    Path to the Python interpreter (defaults to the project venv).

.EXAMPLE
    .\scripts\build.ps1
    .\scripts\build.ps1 -PythonExe "C:\Python313\python.exe"
#>
param(
    [string]$PythonExe = '.\.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ── 0. Sanity checks ──────────────────────────────────────────────────────────
if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}
if (-not (Test-Path 'BioSeqAnalyzer.spec')) {
    throw "BioSeqAnalyzer.spec not found. Run this script from the project root or scripts/ folder."
}

# ── 1. Ensure PyInstaller is installed ────────────────────────────────────────
Write-Host "[1/4] Checking/installing PyInstaller..."
& $PythonExe -m pip install --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

# ── 2. Clean previous artifacts ───────────────────────────────────────────────
Write-Host "[2/4] Cleaning build artifacts..."
Remove-Item -Recurse -Force build  -ErrorAction SilentlyContinue
Remove-Item -Force dist\BioSeqAnalyzer.exe -ErrorAction SilentlyContinue

# ── 3. Run PyInstaller ────────────────────────────────────────────────────────
Write-Host "[3/4] Running PyInstaller (this takes a few minutes the first time)..."
& $PythonExe -m PyInstaller BioSeqAnalyzer.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit $LASTEXITCODE). Check the output above for details."
}

# ── 4. Verify output ──────────────────────────────────────────────────────────
Write-Host "[4/4] Verifying output..."
$exe = Join-Path $root 'dist\BioSeqAnalyzer.exe'
if (-not (Test-Path $exe)) {
    throw "Build did not produce: $exe"
}

$sizeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build SUCCESS" -ForegroundColor Green
Write-Host " Output : $exe" -ForegroundColor Green
Write-Host " Size   : ${sizeMB} MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "NOTES:"
Write-Host "  - softwares/ is NOT bundled. Place BLAST+/MUSCLE/IQ-TREE/trimAl"
Write-Host "    on your system and set paths via the app's settings."
Write-Host "  - User config/bookmarks are saved to %APPDATA%\BioSeqAnalyzer\"
Write-Host "  - To rebuild quickly, skip pip check: run PyInstaller directly:"
Write-Host "      .\.venv\Scripts\python.exe -m PyInstaller BioSeqAnalyzer.spec --noconfirm"
