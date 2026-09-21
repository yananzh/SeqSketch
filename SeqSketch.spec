# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for SeqSketch
# Usage: pyinstaller SeqSketch.spec
# Output: dist/SeqSketch/  (onedir, no console)

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
root = os.path.abspath('.')

# ── Data files to bundle ──────────────────────────────────────────────────────
datas = [
    # QSS stylesheet
    (os.path.join(root, 'styles.qss'),          '.'),
    # Logos (splash + window icons)
    (os.path.join(root, 'start_logo.png'),        '.'),
    (os.path.join(root, 'window_logo.png'),        '.'),
    (os.path.join(root, 'window_logo.ico'),        '.'),
    # Resources directory (modern_theme.qss, etc.)
    (os.path.join(root, 'resources'),            'resources'),
    # Teaching example datasets (cytb, etc.)
    (os.path.join(root, 'examples'),             'examples'),
    # Config template (pre-populated relative paths)
    (os.path.join(root, 'config.ini'),           '.'),
]

# ── External tools (BLAST, IQTree, MAFFT, TrimAl, MUSCLE) ─────────────────────
# Only this platform's tools are bundled: shipping the whole softwares/ tree put
# roughly 375 MB of the other platform's binaries inside every distribution.
# The folder names must stay in sync with utils.app_paths.platform_dir()
# (tests/test_build_spec.py checks this).
if sys.platform.startswith('win'):
    _SOFTWARES_PLATFORM = 'windows'
elif sys.platform == 'darwin':
    _SOFTWARES_PLATFORM = 'Mac'
else:
    _SOFTWARES_PLATFORM = 'linux'

_platform_tools = os.path.join(root, 'softwares', _SOFTWARES_PLATFORM)
if os.path.isdir(_platform_tools):
    datas.append((_platform_tools, os.path.join('softwares', _SOFTWARES_PLATFORM)))
else:
    # Older checkouts keep every tool in a flat softwares/ layout.
    datas.append((os.path.join(root, 'softwares'), 'softwares'))

# logomaker ships data files (font files, etc.)
datas += collect_data_files('logomaker')
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

# ── Exclusions (reduce size) ──────────────────────────────────────────────────
excludes = [
    'tkinter',
    '_tkinter',
    'tcl',
    'tk',
    'Tcl',
    'Tk',
    'test',
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
    'Bio.tests',
    # Build/packaging helpers (never needed at runtime)
    'venv',
    'ensurepip',
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

# Windows-only EXE options: a version resource, an application manifest and an
# .ico icon. macOS wants an .icns instead (the repo does not ship one yet), and
# rejects the other two, so they are added per platform.
_win_exe_options = {}
if sys.platform.startswith('win'):
    _win_exe_options = {
        'icon': os.path.join(root, 'window_logo.ico'),
        'version': os.path.join(root, 'version_info.txt'),
        'manifest': os.path.join(root, 'manifest.xml'),
}

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SeqSketch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **_win_exe_options,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['Qt6*.dll', 'PyQt6*.pyd', 'python*.dll'],
    name='SeqSketch',
)

# macOS: wrap the onedir output in a double-clickable .app bundle. Without it the
# download is a folder whose only launcher is the bare Mach-O executable, which
# Finder will not open by double-click.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SeqSketch.app',
        bundle_identifier='org.seqsketch.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
            'CFBundleShortVersionString': '1.0.0',
        },
    )
