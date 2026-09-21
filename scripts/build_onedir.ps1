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

.PARAMETER Zip
    Also write the release archive that gets published on GitHub Releases:
    dist/SeqSketch-windows.zip on Windows, and on macOS an arch-suffixed
    dist/SeqSketch-Mac-<arch>.zip (a ditto'd .app bundle) so the arm64 and
    x86_64 downloads stay distinguishable.

.EXAMPLE
    .\scripts\build_onedir.ps1
    .\scripts\build_onedir.ps1 -Zip
    .\scripts\build_onedir.ps1 -PythonExe "C:\Python313\python.exe"
#>
param(
    [string]$PythonExe,

    [switch]$Zip
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ── Platform layout ───────────────────────────────────────────────────────────
# Both the bundled tools and the app executable are named per platform:
#   Windows  softwares/windows/...   dist/SeqSketch/SeqSketch.exe
#   macOS    softwares/Mac/...       dist/SeqSketch.app
$IsWindowsHost = $env:OS -eq 'Windows_NT'
$PlatDir = if ($IsWindowsHost) { 'windows' } else { 'Mac' }
$ExeName = if ($IsWindowsHost) { 'SeqSketch.exe' } else { 'SeqSketch' }

if (-not $PythonExe) {
    $PythonExe = if ($IsWindowsHost) {
        Join-Path $root '.venv/Scripts/python.exe'
    } else {
        Join-Path $root '.venv/bin/python'
    }
}

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
Remove-Item -Recurse -Force (Join-Path $root 'build') -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root 'dist/SeqSketch') -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root 'dist/SeqSketch.app') -ErrorAction SilentlyContinue
# Remove Python bytecode cache (prevent stale .pyc from leaking into build)
Get-ChildItem -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter '*.pyc' | Remove-Item -Force -ErrorAction SilentlyContinue
# Remove runtime logs from previous runs
Remove-Item 'startup.log' -Force -ErrorAction SilentlyContinue

# Tool folders are version-numbered (ncbi-blast-2.17.0+, iqtree-3.1.3-Windows), so
# resolve them by name prefix instead of hard-coding a version: tool upgrades then
# need no edit here. The platform-split layout (softwares\windows\<tool>) is
# preferred, with a fallback to the historical flat layout (softwares\<tool>).
function Resolve-ToolDir {
    param([string]$Prefix)
    foreach ($searchRoot in @((Join-Path 'softwares' $PlatDir), 'softwares')) {
        if (-not (Test-Path $searchRoot)) { continue }
        $hit = Get-ChildItem $searchRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "$Prefix*" } |
            Sort-Object Name |
            Select-Object -Last 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

# ── 2.5 Prune bundled tools (keep only runtime-essential files) ─────────────
# NOTE: this prunes softwares\ in place — there is no pristine second copy, and
# softwares/ is gitignored, so a deletion here is not recoverable from git.
Write-Host "[2.5/4] Pruning bundled tool binaries..."

# BLAST: keep only the 6 tools used by SeqSketch + nghttp2.dll (HTTP/2 support
# needed by BLAST's remote query features); remove VDB variants, maskers, docs.
# The small license/metadata text files are deliberately KEPT — deleting them
# strips the redistributions terms out of the folder the app ships with.
$blastKeep = @('blastn', 'blastp', 'blastx', 'tblastn', 'tblastx', 'makeblastdb', 'nghttp2')
$blastRoot = Resolve-ToolDir 'ncbi-blast-'
if ($blastRoot) {
    $blastBin = Join-Path $blastRoot 'bin'
    if (Test-Path $blastBin) {
        foreach ($f in Get-ChildItem $blastBin -File) {
            # "blastn.exe" and "blastn.exe.manifest" both reduce to "blastn"
            $toolName = $f.BaseName -replace '\.exe$', ''
            if ($blastKeep -notcontains $toolName) {
                Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
                Write-Host "  BLAST removed: $($f.Name)"
            }
        }
    }
    Remove-Item (Join-Path $blastRoot 'doc') -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  BLAST pruned: $blastRoot"
} else {
    Write-Warning "  No ncbi-blast-* folder under softwares/ - BLAST prune skipped"
}

# IQ-TREE: remove example/model files (only bin/ + DLL are needed at runtime)
$iqtreeRoot = Resolve-ToolDir 'iqtree-'
if ($iqtreeRoot) {
    @('example.cf', 'example.nex', 'example.phy', 'models.nex') | ForEach-Object {
        Remove-Item (Join-Path $iqtreeRoot $_) -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Warning "  No iqtree-* folder under softwares/ - IQ-TREE prune skipped"
}

# ── 3. Build ──────────────────────────────────────────────────────────────────
Write-Host "[3/4] Building onedir (this takes a few minutes the first time)..."
& $PythonExe -m PyInstaller SeqSketch.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit $LASTEXITCODE). Check output above."
}

# ── 4. Verify + Analyze ───────────────────────────────────────────────────────
Write-Host "[4/4] Verifying output..."
$distDir = Join-Path $root 'dist/SeqSketch'
$exe = Join-Path $distDir $ExeName
if (-not (Test-Path $exe)) {
    throw "Build did not produce: $exe"
}

# Licence material next to the launcher, where a recipient will actually see it.
# SeqSketch.spec already bundles both files into _internal/, but these copies put
# them in the portable folder listing alongside the executable.
foreach ($name in 'LICENSE', 'THIRD-PARTY-NOTICES.md') {
    $source = Join-Path $root $name
    if (Test-Path $source) {
        Copy-Item $source (Join-Path $distDir $name) -Force
    }
}
$dirSize = [math]::Round(
    (Get-ChildItem -Recurse $distDir | Measure-Object -Property Length -Sum).Sum / 1MB, 1
)

# ── Size breakdown ────────────────────────────────────────────
$internal = Join-Path $distDir '_internal'
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

# ── 5. Release archive (optional) ─────────────────────────────────────────────
$artifact = $null
if ($Zip) {
    # macOS ships two builds (Apple Silicon and Intel), so the arch has to be in
    # the name: uname -m gives "arm64" or "x86_64".
    $archSuffix = if ($IsWindowsHost) { '' } else { '-' + (uname -m) }
    $artifact = Join-Path $root "dist/SeqSketch-$PlatDir$archSuffix.zip"
    Remove-Item $artifact -Force -ErrorAction SilentlyContinue
    if ($IsWindowsHost) {
        Compress-Archive -Path $distDir -DestinationPath $artifact -CompressionLevel Optimal
    } else {
        $app = Join-Path $root 'dist/SeqSketch.app'
        if (-not (Test-Path $app)) {
            throw "Expected the BUNDLE() output at $app - check SeqSketch.spec."
        }
        # ditto preserves symlinks, permissions and the bundle bit; a plain zip
        # of a .app produces an app that macOS refuses to launch.
        ditto -c -k --sequesterRsrc --keepParent $app $artifact
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build SUCCESS" -ForegroundColor Green
Write-Host " Output : $distDir" -ForegroundColor Green
Write-Host " Size   : ${dirSize} MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Portable distribution ready:"
Write-Host "  dist/SeqSketch/  <- copy this folder anywhere"
Write-Host ""
Write-Host "Contents:"
Write-Host ("  {0,-20}- launch (no console)" -f $ExeName)
Write-Host "  LICENSE              - GPL-3.0 text for this project"
Write-Host "  THIRD-PARTY-NOTICES.md - licences of the bundled tools and libraries"
Write-Host "  _internal/           - Python, Qt and the bundled tools"
Write-Host "  _internal/third_party_licenses/ - full licence texts for the libraries"
Write-Host "  _internal/config.ini - optional tool path overrides"
Write-Host "  user_data/           - created on first run"
Write-Host ""
Write-Host "Note: UPX compression is ENABLED for non-Qt binaries." -ForegroundColor DarkYellow
Write-Host "      If you encounter AV false-positives, rebuild with --noupx." -ForegroundColor DarkYellow

if ($artifact) {
    $artifactMb = [math]::Round((Get-Item $artifact).Length / 1MB, 1)
    $artifactHash = (Get-FileHash $artifact -Algorithm SHA256).Hash
    Write-Host ""
    Write-Host "Release artifact: $artifact" -ForegroundColor Green
    Write-Host "  Size   : $artifactMb MB"
    Write-Host "  SHA256 : $artifactHash"
    Write-Host ""
    Write-Host "Attach it to a GitHub release with:" -ForegroundColor Cyan
    Write-Host "  gh release upload <tag> `"$artifact`" --clobber"
}
