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
Write-Host "[1/4] Checking/installing PyInstaller..."
& $PythonExe -m pip install --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

# ── 2. Pre-clean ──────────────────────────────────────────────────────────────
Write-Host "[2/4] Pre-cleaning build artifacts..."
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\SeqSketch -ErrorAction SilentlyContinue
# Remove Python bytecode cache (prevent stale .pyc from leaking into build)
Get-ChildItem -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter '*.pyc' | Remove-Item -Force -ErrorAction SilentlyContinue
# Remove runtime logs from previous runs
Remove-Item 'startup.log' -Force -ErrorAction SilentlyContinue

# ── 2.5 Prune bundled tools (keep only runtime-essential files) ─────────────
Write-Host "[2.5/4] Pruning bundled tool binaries..."
# BLAST: keep only the 6 tools used by SeqSketch; remove VDB variants, maskers, docs
$blastBin = 'softwares\ncbi-blast-2.17.0+\bin'
$blastKeep = @('blastn', 'blastp', 'blastx', 'tblastn', 'tblastx', 'makeblastdb')
if (Test-Path $blastBin) {
    $blastAll = Get-ChildItem $blastBin -File
    foreach ($f in $blastAll) {
        $keep = $false
        foreach ($tool in $blastKeep) {
            if ($f.BaseName -eq $tool -or $f.BaseName -eq "$tool.exe") { $keep = $true; break }
        }
        if (-not $keep) {
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            Write-Host "  BLAST removed: $($f.Name)"
        }
    }
    # Remove BLAST doc folder and metadata files
    Remove-Item 'softwares\ncbi-blast-2.17.0+\doc' -Recurse -Force -ErrorAction SilentlyContinue
    @('BLAST_PRIVACY', 'ChangeLog', 'LICENSE', 'ncbi_package_info', 'README') | ForEach-Object {
        Remove-Item "softwares\ncbi-blast-2.17.0+\$_" -Force -ErrorAction SilentlyContinue
    }
}
# IQ-TREE: remove example/model files (only bin/ + DLL are needed at runtime)
$iqtreeRoot = 'softwares\iqtree-3.0.1-Windows'
@('example.cf', 'example.nex', 'example.phy', 'models.nex') | ForEach-Object {
    Remove-Item "$iqtreeRoot\$_" -Force -ErrorAction SilentlyContinue
}

# ── 3. Build ──────────────────────────────────────────────────────────────────
Write-Host "[3/4] Building onedir (this takes a few minutes the first time)..."
& $PythonExe -m PyInstaller SeqSketch.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit $LASTEXITCODE). Check output above."
}

# ── 4. Verify + Analyze ───────────────────────────────────────────────────────
Write-Host "[4/4] Verifying output..."
$exe = Join-Path $root 'dist\SeqSketch\SeqSketch.exe'
if (-not (Test-Path $exe)) {
    throw "Build did not produce: $exe"
}
$dirSize = [math]::Round(
    (Get-ChildItem -Recurse (Join-Path $root 'dist\SeqSketch') |
        Measure-Object -Property Length -Sum).Sum / 1MB, 1
)

# ── Size breakdown ────────────────────────────────────────────────────────────
$internal = Join-Path $root 'dist\SeqSketch\_internal'
if (Test-Path $internal) {
    Write-Host "`n── Size breakdown (_internal/) ──" -ForegroundColor Cyan
    # Top 10 directories by size
    Get-ChildItem -Directory $internal -ErrorAction SilentlyContinue |
        ForEach-Object {
            $sz = [math]::Round(
                (Get-ChildItem -Recurse $_.FullName -ErrorAction SilentlyContinue |
                    Measure-Object -Property Length -Sum).Sum / 1MB, 1
            )
            [PSCustomObject]@{ Dir = $_.Name; MB = $sz }
        } |
        Sort-Object MB -Descending |
        Select-Object -First 10 |
        Format-Table -AutoSize
    # Top 10 file extensions by size
    Write-Host "Top 10 extensions by size:" -ForegroundColor Cyan
    Get-ChildItem -Recurse -File $internal -ErrorAction SilentlyContinue |
        Group-Object Extension |
        ForEach-Object {
            [PSCustomObject]@{ Ext = $_.Name; MB = [math]::Round(($_.Group | Measure-Object Length -Sum).Sum / 1MB, 2); Count = $_.Count }
        } |
        Sort-Object MB -Descending |
        Select-Object -First 10 |
        Format-Table -AutoSize
}

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
Write-Host ""
Write-Host "Note: UPX compression is ENABLED for non-Qt binaries." -ForegroundColor DarkYellow
Write-Host "      If you encounter AV false-positives, rebuild with --noupx." -ForegroundColor DarkYellow
