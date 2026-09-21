<#
.SYNOPSIS
    Package one platform's bundled tools into a release asset.

.DESCRIPTION
    softwares/ holds ~580 MB of third-party binaries and is gitignored, so it is
    NOT committed. Instead the tools travel as a GitHub Release asset and
    scripts/fetch_softwares.ps1 pulls them into a fresh checkout.

    Run this after installing or upgrading a tool, then upload the archive:

        gh release upload tools-v1 dist/softwares-windows.zip --clobber

    The archive holds the *contents* of softwares/<platform>, so extracting it
    back into softwares/<platform> restores the layout the app expects.

.PARAMETER Platform
    Which bundle to package. Defaults to the current OS.

.PARAMETER OutDir
    Where to write the archive. Defaults to dist/ (gitignored).

.EXAMPLE
    .\scripts\pack_softwares.ps1
    .\scripts\pack_softwares.ps1 -Platform Mac
#>
param(
    [ValidateSet('windows', 'Mac')]
    [string]$Platform,

    [string]$OutDir = 'dist'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $Platform) {
    $Platform = if ($env:OS -eq 'Windows_NT') { 'windows' } else { 'Mac' }
}

$source = Join-Path 'softwares' $Platform
if (-not (Test-Path $source)) {
    throw "Nothing to package: $source does not exist."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$archive = Join-Path $OutDir "softwares-$Platform.zip"
Remove-Item $archive -Force -ErrorAction SilentlyContinue

Write-Host "Packaging $source ..."
Compress-Archive -Path (Join-Path $source '*') -DestinationPath $archive -CompressionLevel Optimal

$item = Get-Item $archive
$hash = (Get-FileHash $archive -Algorithm SHA256).Hash

Write-Host ""
Write-Host "Archive : $archive"
Write-Host "Size    : $([math]::Round($item.Length / 1MB, 1)) MB"
Write-Host "SHA256  : $hash"
Write-Host ""
Write-Host "Upload it (the repo is private, so this needs gh auth):" -ForegroundColor Cyan
Write-Host "  gh release upload tools-v1 $archive --clobber"
Write-Host ""
Write-Host "Press the release tag once if it does not exist yet:" -ForegroundColor Cyan
Write-Host "  gh release create tools-v1 --title 'Bundled tools' --notes 'External tool bundles for SeqSketch'"
