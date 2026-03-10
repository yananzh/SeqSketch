param(
    [ValidateSet('balanced', 'small', 'fast')]
    [string]$Profile = 'balanced',

    [string]$PythonExe = '.\.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

Write-Host "[1/4] Installing build dependencies..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install nuitka zstandard ordered-set

# Common Nuitka args for a GUI onefile build.
$args = @(
    '-m', 'nuitka',
    'main.py',
    '--standalone',
    '--onefile',
    '--zig',
    '--enable-plugin=pyqt6',
    '--windows-console-mode=disable',
    '--assume-yes-for-downloads',
    '--follow-imports',
    '--include-module=primer3.bindings',
    '--include-data-file=styles.qss=styles.qss',
    '--include-data-files=*.png=./',
    '--include-data-dir=resources=resources',
    '--include-data-dir=softwares=softwares',
    '--output-dir=dist',
    '--output-filename=BioSeqAnalyzer.exe',
    '--remove-output'
)

switch ($Profile) {
    'small' {
        # Smaller file, slightly slower startup.
        $args += @(
            '--lto=yes',
            '--python-flag=no_docstrings'
        )
    }
    'fast' {
        # Faster startup, larger file.
        $args += @(
            '--lto=no',
            '--onefile-no-compression'
        )
    }
    default {
        # Balanced startup and size.
        $args += @(
            '--lto=yes'
        )
    }
}

Write-Host "[2/4] Building onefile exe (profile: $Profile)..."
& $PythonExe @args
if ($LASTEXITCODE -ne 0) {
    throw "Nuitka build failed with exit code $LASTEXITCODE"
}

Write-Host "[3/4] Build finished."
$exePath = Join-Path $root 'dist\BioSeqAnalyzer.exe'
if (-not (Test-Path $exePath)) {
    throw "Build did not produce exe: $exePath"
}

Write-Host "[4/4] Output: $exePath"
Write-Host "Tip: run .\dist\BioSeqAnalyzer.exe and verify BLAST/MUSCLE/IQ-TREE/trimAl tabs."
