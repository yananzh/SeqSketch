<#
.SYNOPSIS
    Download the bundled external tools into softwares/<platform>/.

.DESCRIPTION
    softwares/ is gitignored (third-party binaries), so a fresh clone has no
    BLAST / IQ-TREE / MAFFT / MUSCLE / trimAl. The app still starts, but every
    external-tool feature reports "not found" and the two tests that need a real
    bundle skip. Run this once after cloning.

    The archives are attached to a dedicated release tag, so the download URL is
    stable and does not change with app releases. Repack and re-upload after
    upgrading a tool with scripts/pack_softwares.ps1.

    This repository is private: the plain release URL needs authentication, so
    the script prefers the gh CLI (run `gh auth login` once). Use -Archive to
    install from a local copy instead, which needs no network at all.

.PARAMETER Platform
    Which bundle to install. Defaults to the current OS.

.PARAMETER Tag
    Release tag holding the archives. Defaults to tools-v1.

.PARAMETER Archive
    Install from this local .zip instead of downloading it.

.PARAMETER Target
    Directory to extract into. Defaults to softwares/<platform>; override it for
    a throwaway install (CI, tests).

.PARAMETER Force
    Replace an existing bundle in the target directory.

.EXAMPLE
    .\scripts\fetch_softwares.ps1
    .\scripts\fetch_softwares.ps1 -Archive D:\handoff\softwares-windows.zip -Force
#>
param(
    [ValidateSet('windows', 'Mac')]
    [string]$Platform,

    [string]$Tag = 'tools-v1',

    [string]$Archive,

    [string]$Target,

    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $Platform) {
    $Platform = if ($env:OS -eq 'Windows_NT') { 'windows' } else { 'Mac' }
}

# Keep in sync with the origin remote (gh release download needs owner/repo).
$repo = 'yananzh/SeqSketch'

if (-not $Target) {
    $Target = Join-Path 'softwares' $Platform
}

# Patterns rather than exact names: tool folders are version-numbered
# (iqtree-3.1.3-Windows), so pinning a version here would rot. These mirror
# utils/tool_paths.py — each pattern must match at least one extracted file.
$expected = @{
    'windows' = @(
        'ncbi-blast-*/bin/blastn.exe',
        'iqtree-*/bin/iqtree3.exe',
        'mafft*/mafft.bat',
        'trimAl*/trimal.exe',
        'muscle*'
    )
    'Mac' = @(
        'ncbi-blast-*/bin/blastn',
        'iqtree-*/bin/iqtree3',
        'mafft*/mafft.bat',
        'trimAl*/bin/trimal',
        'muscle*'
    )
}

if ((Test-Path $Target) -and -not $Force) {
    $existing = (Get-ChildItem $Target -Force | Measure-Object).Count
    if ($existing -gt 0) {
        throw "$Target already exists and is not empty. Re-run with -Force to replace it."
    }
}

$asset = "softwares-$Platform.zip"
$tempArchive = $null

if (-not $Archive) {
    $downloadDir = Join-Path ([System.IO.Path]::GetTempPath()) "seqsketch-$([guid]::NewGuid())"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $Archive = Join-Path $downloadDir $asset
    $tempArchive = $Archive

    if (Get-Command gh -ErrorAction SilentlyContinue) {
        Write-Host "Downloading $asset from release $Tag via gh ..."
        gh release download $Tag --repo $repo --pattern $asset --dir $downloadDir --clobber
        if ($LASTEXITCODE -ne 0) {
            throw "gh release download failed. Is the '$Tag' release published and are you authenticated (gh auth login)?"
        }
    } else {
        $url = "https://github.com/$repo/releases/download/$Tag/$asset"
        Write-Host "gh not found; trying $url"
        Write-Host "A private repository needs a token for this to work." -ForegroundColor Yellow
        try {
            Invoke-WebRequest -Uri $url -OutFile $Archive -UseBasicParsing
        } catch {
            throw "Download failed. Either install the GitHub CLI (gh auth login) or pass -Archive <local zip>."
        }
    }
}

if (-not (Test-Path $Archive)) {
    throw "Archive not found: $Archive"
}

if ($Force -and (Test-Path $Target)) {
    Remove-Item $Target -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Target | Out-Null

Write-Host "Extracting into $Target ..."
Expand-Archive -Path $Archive -DestinationPath $Target -Force

$missing = @()
foreach ($pattern in $expected[$Platform]) {
    if (-not (Test-Path (Join-Path $Target $pattern))) {
        $missing += $pattern
    }
}

if ($tempArchive -and (Test-Path (Split-Path -Parent $tempArchive))) {
    Remove-Item (Split-Path -Parent $tempArchive) -Recurse -Force -ErrorAction SilentlyContinue
}

if ($missing) {
    throw "Extracted bundle is incomplete. Missing: $($missing -join ', ')"
}

$sizeMb = [math]::Round(
    (Get-ChildItem $Target -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB,
    1
)
Write-Host ""
Write-Host ("Done: $Target ({0} MB)" -f $sizeMb) -ForegroundColor Green
Write-Host "Verify with: py -m pytest tests/test_tool_paths.py -q"
