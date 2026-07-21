<#
.SYNOPSIS
    Build SeqSketch onedir (portable, all tools bundled).

.DESCRIPTION
    Uses PyInstaller with SeqSketch.spec (onedir mode).
    Produces: dist\SeqSketch\  (directory with SeqSketch.exe + deps)

    softwares/ IS bundled inside the output directory.
    config.ini IS bundled with pre-configured relative paths.

.PARAMETER PythonExe
    Path to the Python interpreter (defaults to the project venv).

.EXAMPLE
    .\scripts\build_onedir.ps1
    .\scripts\build_onedir.ps1 -PythonExe "C:\Python313\python.exe"
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
if (-not (Test-Path 'SeqSketch.spec')) {
    throw "SeqSketch.spec not found. Run from project root."
}

# ── 1. Ensure PyInstaller ─────────────────────────────────────────────────────
Write-Host "[1/3] Checking/installing PyInstaller..."
& $PythonExe -m pip install --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

# ── 2. Clean + Build ──────────────────────────────────────────────────────────
Write-Host "[2/3] Building onedir (this takes a few minutes the first time)..."
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\SeqSketch -ErrorAction SilentlyContinue
& $PythonExe -m PyInstaller SeqSketch.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit $LASTEXITCODE). Check output above."
}

# ── 3. Verify ─────────────────────────────────────────────────────────────────
Write-Host "[3/3] Verifying output..."
$exe = Join-Path $root 'dist\SeqSketch\SeqSketch.exe'
if (-not (Test-Path $exe)) {
    throw "Build did not produce: $exe"
}
$dirSize = [math]::Round(
    (Get-ChildItem -Recurse (Join-Path $root 'dist\SeqSketch') |
        Measure-Object -Property Length -Sum).Sum / 1MB, 1
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build SUCCESS" -ForegroundColor Green
Write-Host " Output : dist\SeqSketch\" -ForegroundColor Green
Write-Host " Size   : ${dirSize} MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Portable distribution ready:"
Write-Host "  dist\SeqSketch\  <- copy this folder anywhere"
Write-Host ""
Write-Host "Contents:"
Write-Host "  SeqSketch.exe   - launch (no console)"
Write-Host "  config.ini           - tool paths (editable)"
Write-Host "  softwares/           - BLAST, IQTree, MAFFT, TrimAl, MUSCLE"
Write-Host "  user_data/           - created on first run"
