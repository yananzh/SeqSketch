# PyInstaller One-Directory Portable Build — Design

Date: 2026-06-07  
Status: approved

## 1. Goal

Replace the Nuitka onefile build with a PyInstaller **onedir** (one-directory) build that bundles all third-party external tools, pre-configures their paths, and supports fully portable execution (USB-drive-friendly, no `%APPDATA%` dependency when frozen).

## 2. Decisions

| Decision | Choice |
|---|---|
| User data location (frozen) | Onedir root → `user_data/` subdirectory |
| External tool path config | Pre-populated `config.ini` in onedir root, with relative paths |
| Nuitka build | Removed; PyInstaller onedir is the sole build path |
| Config write strategy | Runtime reads/writes `config.ini` directly in onedir root |
| Path resolution approach | `sys.executable` for writable root; `sys._MEIPASS` for read-only resources |

## 3. Output Layout

```
dist/BioSeqAnalyzer/
├── BioSeqAnalyzer.exe          # entry point (no console)
├── config.ini                  # pre-populated template; runtime read/write
├── styles.qss                  # bundled resource
├── 窗口logo.png                # window icon
├── 启动界面logo.png            # splash image
├── resources/
│   └── styles/
│       └── modern_theme.qss
├── softwares/                  # external tools (bundled)
│   ├── ncbi-blast-2.17.0+/
│   │   └── bin/
│   ├── iqtree-3.0.1-Windows/
│   │   └── bin/
│   ├── mafft-win_v7.526/
│   │   └── usr/bin/
│   └── trimAl_Windows_v1.5.1/
├── user_data/                  # created at runtime
│   ├── bookmarks.json
│   ├── favorites.json
│   ├── blast_databases.json
│   └── config.json
├── _internal/                  # PyInstaller: Python + site-packages
└── *.dll                       # Qt DLLs
```

## 4. Path Resolution (`utils/app_paths.py`)

### New: `portable_root()`

```python
def portable_root() -> str:
    """Writable-data root. Frozen → exe directory; dev → project root."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

### Changed: `user_data_dir()`

| Mode | Old | New |
|---|---|---|
| `python main.py` | `%APPDATA%/BioSeqAnalyzer/` | unchanged |
| Frozen (onedir) | `%APPDATA%/BioSeqAnalyzer/` | `<onedir>/user_data/` |

### Unchanged

- `runtime_root()` — uses `sys._MEIPASS` when frozen (points to onedir root for PyInstaller onedir)
- `resource_path()` — always read-only, always via `runtime_root()`

### Path resolution table

| API | Dev (`python main.py`) | Frozen (onedir) |
|---|---|---|
| `runtime_root()` | project root | `sys._MEIPASS` (onedir root) |
| `portable_root()` | project root | `os.path.dirname(sys.executable)` |
| `resource_path("styles.qss")` | `<project>/styles.qss` | `<onedir>/styles.qss` |
| `user_data_dir()` | `%APPDATA%/BioSeqAnalyzer/` | `<onedir>/user_data/` |
| `config.ini` (blast_config) | `<project>/config.ini` | `<onedir>/config.ini` |

## 5. `config.ini` Template

Shipped inside the onedir root, pre-populated with relative paths:

```ini
[BLAST]
bin_dir = softwares/ncbi-blast-2.17.0+/bin

[IQTree]
bin_dir = softwares/iqtree-3.0.1-Windows/bin

[MAFFT]
bin_dir = softwares/mafft-win_v7.526/usr/bin

[TrimAl]
bin_dir = softwares/trimAl_Windows_v1.5.1
```

All paths are relative to the onedir root. At runtime, `blast_config.py` (and equivalent resolvers for IQTree/MAFFT/TrimAl) resolve them via `portable_root()`:

```python
# blast_config.py — frozen path
if getattr(sys, "frozen", False):
    CONFIG_FILE = os.path.join(portable_root(), "config.ini")
```

Fallback: if `config.ini` is missing or the path is invalid, auto-detect by scanning `softwares/` (preserving existing `_detect_bundled_bin()` logic, extended to IQTree/MAFFT/TrimAl).

## 6. PyInstaller `.spec` Changes

### Key diffs from current `BioSeqAnalyzer.spec`

| Aspect | Current | New |
|---|---|---|
| Mode | `onefile=True` | `onefile=False` |
| Output | `EXE()` only | `EXE()` + `COLLECT()` |
| `softwares/` | excluded | included in `datas` |
| `config.ini` | not bundled | bundled in `datas` as template |
| `upx_exclude` | explicit DLL list | `'Qt6*.dll'` wildcard |

### datas additions

```python
datas += [
    (os.path.join(root, 'softwares'), 'softwares'),
    (os.path.join(root, 'config.ini'), '.'),
]
```

### Output structure

```python
exe = EXE(pyz, ..., console=False, icon=..., onefile=False)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True,
    upx_exclude=['Qt6*.dll'],
    name='BioSeqAnalyzer',
)
```

`hiddenimports` and `excludes` lists remain unchanged.

## 7. Affected Files

| File | Change |
|---|---|
| `utils/app_paths.py` | Add `portable_root()`; modify `user_data_dir()` frozen branch |
| `BioSeqAnalyzer.spec` | `onefile=False`, `COLLECT()`, add `softwares/` + `config.ini` to datas |
| `config.ini` | Add `[IQTree]`, `[MAFFT]`, `[TrimAl]` sections with relative paths |
| `modules/blast_config.py` | Frozen: read `config.ini` from `portable_root()` |
| `modules/iqtree_tab.py` | Add config.ini lookup + auto-detect fallback for IQTree path |
| `modules/multiple_sequence_alignment_tab.py` | Add config.ini lookup + auto-detect fallback for MAFFT path |
| `modules/trimal_tab.py` | Add config.ini lookup + auto-detect fallback for TrimAl path |
| `config/settings.py` | Frozen: `config.json` path → `user_data_file("config.json")` |
| `main.py` | Splash logo path → `resource_path("启动界面logo.png")` |
| `main_window.py` | Window icon path → `resource_path("窗口logo.png")` |
| `scripts/build_windows_onefile.ps1` | **Removed** |
| `scripts/build_windows_onefile.bat` | **Removed** |
| `scripts/build.ps1` | Updated to call PyInstaller with `BioSeqAnalyzer.spec` (onedir) |
| `scripts/build_onedir.ps1` | **New** — primary build script |
| `AGENTS.md` | Update build commands |
| `CLAUDE.md` | Update build commands |

## 8. Build Script (`scripts/build_onedir.ps1`)

```powershell
param([string]$PythonExe = '.\.venv\Scripts\python.exe')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# [1/3] Ensure PyInstaller
Write-Host "[1/3] Checking/installing PyInstaller..."
& $PythonExe -m pip install --quiet --upgrade pyinstaller

# [2/3] Build
Write-Host "[2/3] Building onedir..."
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\BioSeqAnalyzer -ErrorAction SilentlyContinue
& $PythonExe -m PyInstaller BioSeqAnalyzer.spec --noconfirm

# [3/3] Verify
$exe = Join-Path $root 'dist\BioSeqAnalyzer\BioSeqAnalyzer.exe'
if (-not (Test-Path $exe)) { throw "Build did not produce: $exe" }
$sizeMB = [math]::Round((Get-ChildItem -Recurse (Join-Path $root 'dist\BioSeqAnalyzer') | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Build SUCCESS — dist\BioSeqAnalyzer\ ($sizeMB MB)" -ForegroundColor Green
```

## 9. Error Handling

- `portable_root()` never fails — falls back to `__file__`-based path in dev mode
- `user_data_dir()` always calls `os.makedirs(..., exist_ok=True)`, so first-run creation is safe
- External tool path resolvers follow a strict fallback chain: `config.ini` → auto-detect `softwares/` → empty (user prompted in UI)
- `config.ini` read failures log a warning and fall through to auto-detect; write failures log an error but do not crash

## 10. Testing

### Automated

- **New**: `tests/test_build_spec.py` — validates `BioSeqAnalyzer.spec` can be parsed, `onefile=False`, `COLLECT` present, `softwares/` and `config.ini` in datas
- **Existing**: `tests/test_dna_analysis_tabs.py` and `tests/test_fasta_tools_tabs.py` must all pass (path compatibility under dev mode)

### Manual smoke

1. Run `.\scripts\build_onedir.ps1`
2. Launch `dist\BioSeqAnalyzer\BioSeqAnalyzer.exe`
3. Verify each external-tool tab finds its binary:
   - BLAST Local: make DB + run search
   - IQTree: open tree tab
   - MAFFT: open alignment tab
   - TrimAl: open trimming tab
4. Verify `user_data/` directory is created in onedir root on first run
5. Verify `config.ini` in onedir root can be edited and changes take effect on restart
