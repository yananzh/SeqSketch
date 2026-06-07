# PyInstaller One-Directory Portable Build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Nuitka onefile build with PyInstaller onedir build that bundles all external tools and supports fully portable USB-drive execution.

**Architecture:** `app_paths.py` gains `portable_root()` (frozen→exe directory, dev→project root). `user_data_dir()` switches from `%APPDATA%` to `<onedir>/user_data/` when frozen. A pre-populated `config.ini` template ships in the onedir root with relative paths to all external tools. Tool tabs read config.ini first, fall back to auto-detection. Build moves from Nuitka `--onefile` to PyInstaller `--onedir` via updated `.spec`.

**Tech Stack:** PyInstaller, Python 3.x, PowerShell build script, configparser for .ini

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `utils/app_paths.py` | Modify | Add `portable_root()`, adapt `user_data_dir()` for frozen |
| `config.ini` | Modify | Add `[IQTree]`, `[MAFFT]`, `[TrimAl]`, `[MUSCLE]` sections |
| `BioSeqAnalyzer.spec` | Modify | `onefile=False`, `COLLECT()`, bundle `softwares/` + `config.ini` |
| `modules/blast_config.py` | Modify | Frozen: read config.ini from `portable_root()` |
| `modules/iqtree_tab.py` | Modify | `IQTREE_EXE` from config.ini + resource_path fallback |
| `modules/mafft_alignment_tab.py` | Modify | `_default_mafft_exe()` from config.ini + resource_path fallback |
| `modules/trimal_tab.py` | Modify | `TRIMAL_EXE` from config.ini + resource_path fallback |
| `modules/multiple_sequence_alignment_tab.py` | Modify | `MUSCLE_EXE` from config.ini + resource_path fallback |
| `main.py` | Modify | Splash logo → `resource_path()` |
| `main_window.py` | Modify | Window icon → `resource_path()` |
| `config/settings.py` | Modify | Frozen: `config.json` → `user_data_file()` |
| `scripts/build_onedir.ps1` | Create | Primary build script |
| `scripts/build_windows_onefile.ps1` | Delete | Remove Nuitka build |
| `scripts/build_windows_onefile.bat` | Delete | Remove Nuitka wrapper |
| `scripts/build.ps1` | Modify | Point to PyInstaller onedir build |
| `AGENTS.md` | Modify | Update build commands |
| `CLAUDE.md` | Modify | Update build commands |
| `tests/test_build_spec.py` | Create | Validate spec structure |
| `docs/superpowers/specs/2026-06-07-pyinstaller-onedir-design.md` | Keep | Reference spec (already written) |

---

### Task 1: Add `portable_root()` and adapt `user_data_dir()` in `app_paths.py`

**Files:**
- Modify: `f:\ui\utils\app_paths.py`

- [ ] **Step 1: Add `portable_root()` function and modify `user_data_dir()`**

Replace the entire file content:

```python
import os
import sys


APP_NAME = "BioSeqAnalyzer"


def runtime_root() -> str:
    """Return the root path that contains bundled runtime resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Build a path inside the runtime resource root."""
    return os.path.join(runtime_root(), *parts)


def portable_root() -> str:
    """Writable-data root.  Frozen → exe directory; dev → project root."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_dir(app_name: str = APP_NAME) -> str:
    """Return writable per-user data directory, creating it if needed.

    In frozen (onedir) mode the directory lives under the exe folder so the
    whole installation stays portable.  In dev mode the legacy %APPDATA%
    location is kept for backwards compatibility.
    """
    if getattr(sys, "frozen", False):
        path = os.path.join(portable_root(), "user_data")
    else:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_file(filename: str, app_name: str = APP_NAME) -> str:
    """Return writable per-user data file path."""
    return os.path.join(user_data_dir(app_name), filename)
```

- [ ] **Step 2: Verify the module imports cleanly**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "from utils.app_paths import portable_root, user_data_dir, resource_path; print('portable_root:', portable_root()); print('user_data_dir:', user_data_dir()); print('resource_path styles.qss:', resource_path('styles.qss'))"
```

Expected: prints paths inside `f:\ui` (dev mode), no errors.

- [ ] **Step 3: Commit**

```bash
git add utils/app_paths.py
git commit -m "feat: add portable_root() and portable user_data_dir for onedir builds"
```

---

### Task 2: Populate `config.ini` with external tool paths

**Files:**
- Modify: `f:\ui\config.ini`

- [ ] **Step 1: Add sections for all external tools**

Replace the entire file content:

```ini
[BLAST]
bin_dir = softwares/ncbi-blast-2.17.0+/bin

[IQTree]
bin_dir = softwares/iqtree-3.0.1-Windows/bin

[MAFFT]
bin_dir = softwares/mafft-win_v7.526

[TrimAl]
bin_dir = softwares/trimAl_Windows_v1.5.1

[MUSCLE]
exe = softwares/muscle-win64.v5.3.exe
```

Note: paths are relative to the onedir root (`portable_root()`).

- [ ] **Step 2: Verify configparser can read it**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print('Sections:', c.sections()); print('BLAST:', c.get('BLAST','bin_dir')); print('IQTree:', c.get('IQTree','bin_dir'))"
```

Expected: `Sections: ['BLAST', 'IQTree', 'MAFFT', 'TrimAl', 'MUSCLE']` with correct values.

- [ ] **Step 3: Commit**

```bash
git add config.ini
git commit -m "feat: add IQTree/MAFFT/TrimAl/MUSCLE sections to config.ini"
```

---

### Task 3: Convert `BioSeqAnalyzer.spec` to onedir mode

**Files:**
- Modify: `f:\ui\BioSeqAnalyzer.spec`

- [ ] **Step 1: Rewrite spec for onedir with softwares/ and config.ini bundled**

Replace the entire file content:

```python
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for BioSeqAnalyzer — onedir portable build
# Usage: pyinstaller BioSeqAnalyzer.spec
# Output: dist/BioSeqAnalyzer/  (directory with BioSeqAnalyzer.exe + all deps)

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
root = os.path.abspath('.')

# ── Data files to bundle ──────────────────────────────────────────────────────
datas = [
    # QSS stylesheet
    (os.path.join(root, 'styles.qss'),          '.'),
    # Logos (splash + window icon)
    (os.path.join(root, '窗口logo.png'),         '.'),
    (os.path.join(root, '启动界面logo.png'),     '.'),
    # Resources directory (modern_theme.qss, etc.)
    (os.path.join(root, 'resources'),            'resources'),
    # External tools (BLAST, IQTree, MAFFT, TrimAl, MUSCLE)
    (os.path.join(root, 'softwares'),            'softwares'),
    # Config template (pre-populated relative paths)
    (os.path.join(root, 'config.ini'),           '.'),
]

# logomaker ships data files (font files, etc.)
datas += collect_data_files('logomaker')
# phytreeviz may include data files
datas += collect_data_files('phytreeviz')
# matplotlib needs its data (fonts, matplotlibrc, etc.)
datas += collect_data_files('matplotlib')
# Bio (biopython) data files
datas += collect_data_files('Bio')
# primer3 needs its src/ directory (thermodynamic parameter files)
datas += collect_data_files('primer3')

# ── Hidden imports (dynamic / conditional imports) ────────────────────────────
hiddenimports = [
    # primer3 Cython extension – imported via importlib at runtime
    'primer3.bindings',
    'primer3.thermoanalysis',
    'primer3.p3helpers',
    'primer3.argdefaults',
    # PyQt6 extras sometimes missed
    'PyQt6.sip',
    'PyQt6.QtPrintSupport',
    # matplotlib PyQt6 backend
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_qt',
    'matplotlib.backends.backend_agg',
    # scipy submodules
    'scipy.special._ufuncs_cxx',
    'scipy._lib.messagestream',
    'scipy.io.matlab.mio5_utils',
    'scipy.io.matlab.streams',
    'scipy.sparse.csgraph._validation',
    'scipy.spatial.transform._rotation_groups',
    # numpy extras
    'numpy.core._dtype_ctypes',
    'numpy.random.common',
    'numpy.random.bounded_integers',
    'numpy.random.entropy',
    # pandas
    'pandas',
    'pandas._libs.tslibs.base',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.timezones',
    # Bio submodules used by tabs
    'Bio.SeqIO',
    'Bio.SeqIO.FastaIO',
    'Bio.SeqUtils',
    'Bio.Align',
    'Bio.Blast',
    'Bio.Blast.NCBIXML',
    'Bio.Data',
    'Bio.Data.CodonTable',
    # phytreeviz
    'phytreeviz',
    # logomaker
    'logomaker',
]
# Collect only the Bio submodules actually used by the app
# (avoid pulling in mmtf, PDB-heavy, etc.)
hiddenimports += [
    'Bio.SeqIO', 'Bio.SeqIO.FastaIO', 'Bio.SeqIO.InsdcIO',
    'Bio.SeqRecord', 'Bio.Seq', 'Bio.SeqUtils',
    'Bio.SeqUtils.ProtParam', 'Bio.SeqUtils.MeltingTemp',
    'Bio.Align', 'Bio.Align.substitution_matrices',
    'Bio.pairwise2',
    'Bio.Blast', 'Bio.Blast.NCBIXML', 'Bio.Blast.NCBIWWW', 'Bio.Blast.Applications',
    'Bio.Data', 'Bio.Data.CodonTable', 'Bio.Data.IUPACData',
    'Bio.Phylo', 'Bio.Phylo.NewickIO', 'Bio.Phylo.NexusIO',
    'Bio.Phylo.BaseTree',
    'Bio.SearchIO', 'Bio.SearchIO.BlastIO',
    'Bio.motifs', 'Bio.Restriction',
    'Bio.Graphics',
    'Bio.Entrez',
]
# Collect only the scipy submodules actually needed
hiddenimports += [
    'scipy.spatial', 'scipy.spatial.distance', 'scipy.spatial.transform',
    'scipy.stats', 'scipy.stats._stats_py',
    'scipy.cluster', 'scipy.cluster.hierarchy',
    'scipy.integrate',
    'scipy.optimize',
    'scipy.interpolate',
    'scipy.sparse', 'scipy.sparse.csgraph',
    'scipy.linalg',
    'scipy.fft',
    'scipy.signal',
    'scipy.ndimage',
]

# ── Exclusions (reduce size) ──────────────────────────────────────────────────
excludes = [
    'tkinter',
    '_tkinter',
    'tcl',
    'tk',
    'Tcl',
    'Tk',
    'test',
    'unittest',
    # Unused matplotlib backends
    'matplotlib.backends.backend_gtk3',
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_gtk4',
    'matplotlib.backends.backend_gtk4agg',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_tkcairo',
    'matplotlib.backends.backend_wxagg',
    'matplotlib.backends.backend_wx',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_ps',
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_pgf',
    # IPython / Jupyter not needed
    'IPython',
    'ipykernel',
    'jupyter',
    'notebook',
    # XML / docutils not needed
    'docutils',
    'xmlrpc',
    # Distutils / setuptools not needed at runtime
    'setuptools',
    'distutils',
    'pkg_resources',
    # Other unused heavy libs
    'wx',
    'gi',
    # Test suites - not needed at runtime
    'scipy.linalg.tests',
    'scipy.stats.tests',
    'scipy.optimize.tests',
    'scipy.signal.tests',
    'scipy.ndimage.tests',
    'scipy.sparse.tests',
    'scipy.spatial.tests',
    'scipy.integrate.tests',
    'scipy.interpolate.tests',
    'scipy.io.tests',
    'scipy.fft.tests',
    'Bio.tests',
]

a = Analysis(
    ['main.py'],
    pathex=[root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BioSeqAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root, '窗口logo.png') if os.path.exists(os.path.join(root, '窗口logo.png')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['Qt6*.dll'],
    name='BioSeqAnalyzer',
)
```

- [ ] **Step 2: Verify spec parses correctly**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); exec(open('BioSeqAnalyzer.spec').read().split('a = Analysis')[0]); print('Spec header OK')"
```

Expected: `Spec header OK` (validates Python syntax and imports).

- [ ] **Step 3: Commit**

```bash
git add BioSeqAnalyzer.spec
git commit -m "feat: convert spec to onedir mode with softwares/ and config.ini bundled"
```

---

### Task 4: Adapt `blast_config.py` for portable config.ini

**Files:**
- Modify: `f:\ui\modules\blast_config.py`

- [ ] **Step 1: Change config file path resolution for frozen mode**

Read the current `_LEGACY_CONFIG_FILE` and `CONFIG_FILE` lines (approximately lines 7-11):

```python
from utils.app_paths import resource_path, user_data_file

_LEGACY_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config.ini"
)
CONFIG_FILE = user_data_file("config.ini")
```

Replace with:

```python
import sys
from utils.app_paths import portable_root, resource_path, user_data_file

_LEGACY_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config.ini"
)

if getattr(sys, "frozen", False):
    CONFIG_FILE = os.path.join(portable_root(), "config.ini")
else:
    CONFIG_FILE = user_data_file("config.ini")
```

- [ ] **Step 2: Verify import and path resolution**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "from modules.blast_config import CONFIG_FILE; print('CONFIG_FILE:', CONFIG_FILE)"
```

Expected: prints `CONFIG_FILE: C:\Users\...\AppData\Roaming\BioSeqAnalyzer\config.ini` (dev mode, %APPDATA% path).

- [ ] **Step 3: Commit**

```bash
git add modules/blast_config.py
git commit -m "feat: read config.ini from portable_root() when frozen"
```

---

### Task 5: Add config.ini lookup to external tool tabs

**Files:**
- Modify: `f:\ui\modules\iqtree_tab.py`
- Modify: `f:\ui\modules\mafft_alignment_tab.py`
- Modify: `f:\ui\modules\trimal_tab.py`
- Modify: `f:\ui\modules\multiple_sequence_alignment_tab.py`

- [ ] **Step 1: Add shared helper for reading tool paths from config.ini**

Create a new helper in `utils/app_paths.py` (append after existing content):

```python
import configparser


def tool_path_from_config(section: str, key: str) -> str | None:
    """Read a tool path from config.ini in portable_root().

    Returns the resolved absolute path, or None if not configured.
    """
    if getattr(sys, "frozen", False):
        config_path = os.path.join(portable_root(), "config.ini")
    else:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.ini",
        )
    if not os.path.isfile(config_path):
        return None
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding="utf-8")
        rel = cfg.get(section, key, fallback=None)
        if rel:
            # Resolve relative to portable_root()
            return os.path.normpath(os.path.join(portable_root(), rel))
    except Exception:
        pass
    return None
```

- [ ] **Step 2: Modify `iqtree_tab.py` — replace `_HERE` + hardcoded path**

Read lines 33-37 of `iqtree_tab.py`:

```python
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IQTREE_EXE = os.path.join(
    _HERE, "softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe"
)
```

Replace with:

```python
from utils.app_paths import resource_path, tool_path_from_config

def _resolve_iqtree_exe() -> str:
    """Resolve IQTree executable path: config.ini → bundled fallback."""
    configured = tool_path_from_config("IQTree", "bin_dir")
    if configured:
        exe = os.path.join(configured, "iqtree3.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe")

IQTREE_EXE = _resolve_iqtree_exe()
```

- [ ] **Step 3: Modify `mafft_alignment_tab.py` — update `_default_mafft_exe()`**

Read lines 31-36 of `mafft_alignment_tab.py`:

```python
def _default_mafft_exe() -> str:
    for name in ("mafft.bat", "mafft-signed.ps1"):
        candidate = resource_path("softwares", "mafft-win", name)
        if os.path.isfile(candidate):
            return candidate
    return resource_path("softwares", "mafft-win", "mafft.bat")
```

Replace with:

```python
from utils.app_paths import resource_path, tool_path_from_config

def _default_mafft_exe() -> str:
    """Resolve MAFFT launcher: config.ini → bundled fallback."""
    configured = tool_path_from_config("MAFFT", "bin_dir")
    if configured:
        for name in ("mafft.bat", "mafft-signed.ps1"):
            candidate = os.path.join(configured, name)
            if os.path.isfile(candidate):
                return candidate
        # also check usr/bin
        for name in ("mafft.bat", "mafft-signed.ps1"):
            candidate = os.path.join(configured, "usr", "bin", name)
            if os.path.isfile(candidate):
                return candidate
    # Fallback: bundled path
    for name in ("mafft.bat", "mafft-signed.ps1"):
        candidate = resource_path("softwares", "mafft-win_v7.526", name)
        if os.path.isfile(candidate):
            return candidate
    return resource_path("softwares", "mafft-win_v7.526", "mafft.bat")
```

- [ ] **Step 4: Modify `trimal_tab.py` — update `TRIMAL_EXE`**

Read line 56 of `trimal_tab.py`:

```python
TRIMAL_EXE = resource_path("softwares", "trimAl_Windows_x86-64", "trimal.exe")
```

Replace with:

```python
def _resolve_trimal_exe() -> str:
    """Resolve trimAl executable: config.ini → bundled fallback."""
    configured = tool_path_from_config("TrimAl", "bin_dir")
    if configured:
        exe = os.path.join(configured, "trimal.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "trimAl_Windows_v1.5.1", "trimal.exe")

TRIMAL_EXE = _resolve_trimal_exe()
```

- [ ] **Step 5: Modify `multiple_sequence_alignment_tab.py` — update `MUSCLE_EXE`**

Read lines 33-35 of `multiple_sequence_alignment_tab.py`:

```python
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSCLE_EXE = os.path.join(_HERE, "softwares", "muscle-win64.v5.3.exe")
CONFIG_INI = user_data_file("config.ini")
```

Replace with:

```python
from utils.app_paths import resource_path, tool_path_from_config

def _resolve_muscle_exe() -> str:
    """Resolve MUSCLE executable: config.ini → bundled fallback."""
    configured = tool_path_from_config("MUSCLE", "exe")
    if configured and os.path.isfile(configured):
        return configured
    return resource_path("softwares", "muscle-win64.v5.3.exe")

MUSCLE_EXE = _resolve_muscle_exe()
```

Also remove the unused `CONFIG_INI = user_data_file("config.ini")` line.

- [ ] **Step 6: Verify all modules import cleanly**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "from modules.iqtree_tab import IQTREE_EXE; print('IQTree:', IQTREE_EXE)"
& f:\ui\.venv\Scripts\python.exe -c "from modules.mafft_alignment_tab import _default_mafft_exe; print('MAFFT:', _default_mafft_exe())"
& f:\ui\.venv\Scripts\python.exe -c "from modules.trimal_tab import TRIMAL_EXE; print('TrimAl:', TRIMAL_EXE)"
& f:\ui\.venv\Scripts\python.exe -c "from modules.multiple_sequence_alignment_tab import MUSCLE_EXE; print('MUSCLE:', MUSCLE_EXE)"
```

Expected: each prints a valid path under `f:\ui\softwares\`.

- [ ] **Step 7: Commit**

```bash
git add utils/app_paths.py modules/iqtree_tab.py modules/mafft_alignment_tab.py modules/trimal_tab.py modules/multiple_sequence_alignment_tab.py
git commit -m "feat: resolve external tool paths from config.ini with resource_path fallback"
```

---

### Task 6: Fix resource path lookups in `main.py` and `main_window.py`

**Files:**
- Modify: `f:\ui\main.py`
- Modify: `f:\ui\main_window.py`

- [ ] **Step 1: `main.py` — splash logo via `resource_path()`**

Read line 30 of `main.py`:

```python
    logo_path = os.path.join(os.path.dirname(__file__), "start_logo.png")
```

Replace with:

```python
    from utils.app_paths import resource_path
    logo_path = resource_path("启动界面logo.png")
```

- [ ] **Step 2: `main_window.py` — find window icon path usage**

Search for icon-related path:

```powershell
rg "窗口logo|setWindowIcon|logo" main_window.py
```

If it uses `os.path.join(os.path.dirname(__file__), ...)` or similar legacy pattern, replace with `resource_path("窗口logo.png")`.

- [ ] **Step 3: Verify imports**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "from main import main; print('main.py imports OK')"
```

- [ ] **Step 4: Commit**

```bash
git add main.py main_window.py
git commit -m "fix: use resource_path() for splash logo and window icon"
```

---

### Task 7: Adapt `config/settings.py` for portable config.json

**Files:**
- Modify: `f:\ui\config\settings.py`

- [ ] **Step 1: Make `config.json` path use `user_data_file` when frozen**

Read the `__init__` method of `Settings` class (around line 10):

```python
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
```

Replace with:

```python
    import sys
    from utils.app_paths import user_data_file

    def __init__(self, config_file: str | None = None):
        if config_file is None:
            if getattr(sys, "frozen", False):
                self.config_file = user_data_file("config.json")
            else:
                self.config_file = "config.json"
        else:
            self.config_file = config_file
```

- [ ] **Step 2: Verify**

```powershell
& f:\ui\.venv\Scripts\python.exe -c "from config.settings import Settings; s=Settings(); print('Config file:', s.config_file)"
```

Expected: `Config file: config.json` (dev mode) — file created in project root.

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "fix: use user_data_file for config.json when frozen"
```

---

### Task 8: Create build script and clean up old scripts

**Files:**
- Create: `f:\ui\scripts\build_onedir.ps1`
- Delete: `f:\ui\scripts\build_windows_onefile.ps1`
- Delete: `f:\ui\scripts\build_windows_onefile.bat`
- Modify: `f:\ui\scripts\build.ps1`

- [ ] **Step 1: Create `scripts/build_onedir.ps1`**

```powershell
<#
.SYNOPSIS
    Build BioSeqAnalyzer onedir (portable, all tools bundled).

.DESCRIPTION
    Uses PyInstaller with BioSeqAnalyzer.spec (onedir mode).
    Produces: dist\BioSeqAnalyzer\  (directory with BioSeqAnalyzer.exe + deps)

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
if (-not (Test-Path 'BioSeqAnalyzer.spec')) {
    throw "BioSeqAnalyzer.spec not found. Run from project root."
}

# ── 1. Ensure PyInstaller ─────────────────────────────────────────────────────
Write-Host "[1/3] Checking/installing PyInstaller..."
& $PythonExe -m pip install --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

# ── 2. Clean + Build ──────────────────────────────────────────────────────────
Write-Host "[2/3] Building onedir (this takes a few minutes the first time)..."
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\BioSeqAnalyzer -ErrorAction SilentlyContinue
& $PythonExe -m PyInstaller BioSeqAnalyzer.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit $LASTEXITCODE). Check output above."
}

# ── 3. Verify ─────────────────────────────────────────────────────────────────
Write-Host "[3/3] Verifying output..."
$exe = Join-Path $root 'dist\BioSeqAnalyzer\BioSeqAnalyzer.exe'
if (-not (Test-Path $exe)) {
    throw "Build did not produce: $exe"
}
$dirSize = [math]::Round(
    (Get-ChildItem -Recurse (Join-Path $root 'dist\BioSeqAnalyzer') |
        Measure-Object -Property Length -Sum).Sum / 1MB, 1
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build SUCCESS" -ForegroundColor Green
Write-Host " Output : dist\BioSeqAnalyzer\" -ForegroundColor Green
Write-Host " Size   : ${dirSize} MB" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Portable distribution ready:"
Write-Host "  dist\BioSeqAnalyzer\  ← copy this folder anywhere"
Write-Host ""
Write-Host "Contents:"
Write-Host "  BioSeqAnalyzer.exe   — launch (no console)"
Write-Host "  config.ini           — tool paths (editable)"
Write-Host "  softwares/           — BLAST, IQTree, MAFFT, TrimAl, MUSCLE"
Write-Host "  user_data/           — created on first run"
```

- [ ] **Step 2: Update `scripts/build.ps1`**

Replace the content to call the new script:

```powershell
<#
.SYNOPSIS
    Build BioSeqAnalyzer onedir (portable, all tools bundled).
    Shortcut wrapper for .\scripts\build_onedir.ps1
#>
param(
    [string]$PythonExe = '.\.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& "$PSScriptRoot\build_onedir.ps1" -PythonExe $PythonExe
exit $LASTEXITCODE
```

- [ ] **Step 3: Delete old Nuitka scripts**

```powershell
Remove-Item f:\ui\scripts\build_windows_onefile.ps1
Remove-Item f:\ui\scripts\build_windows_onefile.bat
```

- [ ] **Step 4: Dry-run build script (syntax check only, no actual build)**

```powershell
powershell -Command "Get-Command f:\ui\scripts\build_onedir.ps1"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/build_onedir.ps1 scripts/build.ps1
git rm scripts/build_windows_onefile.ps1 scripts/build_windows_onefile.bat
git commit -m "feat: add onedir build script, remove Nuitka build scripts"
```

---

### Task 9: Write spec validation test

**Files:**
- Create: `f:\ui\tests\test_build_spec.py`

- [ ] **Step 1: Create the test file**

```python
"""Validate BioSeqAnalyzer.spec structure for onedir builds."""
import os
import sys
import pytest


SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "BioSeqAnalyzer.spec"
)


def test_spec_file_exists():
    """The .spec file must exist in the project root."""
    assert os.path.isfile(SPEC_PATH), f"Missing: {SPEC_PATH}"


def test_spec_is_valid_python():
    """The .spec file must be syntactically valid Python."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    compile(source, SPEC_PATH, "exec")


def test_spec_onedir_not_onefile():
    """The spec must use onedir mode (onefile=False), not onefile."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "onefile=True" not in source, "Spec must NOT use onefile=True"
    assert "COLLECT(" in source, "Spec must contain COLLECT() for onedir output"


def test_spec_bundles_softwares():
    """softwares/ must be listed in datas for bundling."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'softwares'" in source or '"softwares"' in source, (
        "softwares/ must be in datas"
    )


def test_spec_bundles_config_ini():
    """config.ini must be listed in datas for bundling."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'config.ini'" in source or '"config.ini"' in source, (
        "config.ini must be in datas"
    )


def test_spec_console_disabled():
    """The exe must run without a console window."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "console=False" in source, "console must be False for GUI app"


def test_spec_excludes_tkinter():
    """tkinter must be excluded (not needed for PyQt6 app)."""
    with open(SPEC_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert "'tkinter'" in source or '"tkinter"' in source, (
        "tkinter must be in excludes"
    )
```

- [ ] **Step 2: Run the tests**

```powershell
py -m pytest tests/test_build_spec.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 3: Run full existing test suites to confirm no regressions**

```powershell
py -m pytest tests/test_dna_analysis_tabs.py -q
py -m pytest tests/test_fasta_tools_tabs.py -q
```

Expected: all existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_build_spec.py
git commit -m "test: add spec structure validation for onedir build"
```

---

### Task 10: Update documentation

**Files:**
- Modify: `f:\ui\AGENTS.md`
- Modify: `f:\ui\CLAUDE.md`

- [ ] **Step 1: Update `AGENTS.md` build section**

Read the Verified Commands section. Replace the Nuitka build line:

```
Build the Windows one-file executable with Nuitka:

```powershell
.\scripts\build_windows_onefile.ps1 -Profile balanced
```
```

With:

```
Build the Windows portable onedir distribution with PyInstaller:

```powershell
.\scripts\build_onedir.ps1
```

The output `dist/BioSeqAnalyzer/` is a self-contained portable folder — copy it anywhere.
```

- [ ] **Step 2: Update `CLAUDE.md` Quick Reference**

Replace:

```
Build Windows executable:
```powershell
.\scripts\build_windows_onefile.ps1 -Profile balanced
```
```

With:

```
Build Windows portable distribution:
```powershell
.\scripts\build_onedir.ps1
```
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: update build commands for PyInstaller onedir"
```

---

### Task 11: Full build verification (manual)

- [ ] **Step 1: Run the full build**

```powershell
.\scripts\build_onedir.ps1
```

Expected: `Build SUCCESS — dist\BioSeqAnalyzer\ (XXX MB)`.

- [ ] **Step 2: Verify output structure**

```powershell
Get-ChildItem dist\BioSeqAnalyzer -Depth 1
```

Expected: `BioSeqAnalyzer.exe`, `config.ini`, `styles.qss`, `窗口logo.png`, `启动界面logo.png`, `resources/`, `softwares/`, `_internal/`, `*.dll`.

- [ ] **Step 3: Verify softwares bundled correctly**

```powershell
Test-Path dist\BioSeqAnalyzer\softwares\ncbi-blast-2.17.0+\bin\blastn.exe
Test-Path dist\BioSeqAnalyzer\softwares\iqtree-3.0.1-Windows\bin\iqtree3.exe
Test-Path dist\BioSeqAnalyzer\softwares\mafft-win_v7.526\mafft.bat
Test-Path dist\BioSeqAnalyzer\softwares\trimAl_Windows_v1.5.1\trimal.exe
Test-Path dist\BioSeqAnalyzer\softwares\muscle-win64.v5.3.exe
```

Expected: all `True`.

- [ ] **Step 4: Launch and smoke test**

```powershell
Start-Process dist\BioSeqAnalyzer\BioSeqAnalyzer.exe
```

Manual checks:
1. App launches without console window
2. BLAST Local tab: tool path auto-populated
3. IQTree tab: executable path auto-populated
4. MAFFT tab: launcher path auto-populated
5. TrimAl tab: executable path auto-populated
6. MSA (MUSCLE) tab: executable path auto-populated
7. `user_data/` directory created in `dist/BioSeqAnalyzer/`
8. `config.ini` can be edited and changes take effect on restart

- [ ] **Step 5: Final commit (if any fixes from smoke test)**

```bash
git add -A
git commit -m "chore: final adjustments from onedir build smoke test"
```
