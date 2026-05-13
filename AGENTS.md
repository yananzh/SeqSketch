# BioSeqAnalyzer — Agent Instructions

PyQt6-based bioinformatics sequence analysis desktop app (Python). See [readme.txt](readme.txt) for feature overview.

## Setup & Running

```bash
pip install -r requirements.txt
python main.py
```

**Build executable** (Windows, requires Nuitka):
```powershell
.\scripts\build_windows_onefile.ps1 -Profile balanced
# Output: dist\BioSeqAnalyzer.exe
```

## Architecture

Tab-based UI. Each feature is an independent tab module that is lazy-loaded on demand.

```
main.py              → QApplication bootstrap, splash screen
main_window.py       → MainWindow (QMainWindow): central QTabWidget, tab management
menus.py             → Menu bar: QActions wired to MainWindow.open_*_tab() methods
modules/             → One file per feature tab: *_tab.py → *Tab class
utils/               → Shared utilities (paths, base classes)
config/settings.py   → JSON settings manager (dot-notation access)
config.ini           → External tool paths (BLAST bin dir, etc.)
softwares/           → Bundled binaries: BLAST 2.17, IQTree 3.0.1, TrimAl
```

## Adding a New Tab — Required Steps

1. **Create** `modules/my_feature_tab.py` with a `MyFeatureTab(BaseTabWidget)` class (see pattern below).
2. **Add** `open_my_feature_tab()` method to `MainWindow` in `main_window.py`.
3. **Add** a `QAction` wired to that method in the appropriate menu in `menus.py`.
4. **Export** the class in `modules/__init__.py` `__all__`.

## Module / Tab Pattern

All tabs inherit from `BaseTabWidget` (in `utils/common_components.py`). Heavy work runs in a `*Worker(BaseWorker)` QThread subclass.

```python
from PyQt6.QtCore import pyqtSignal, QThread
from utils.common_components import BaseTabWidget, BaseWorker

class MyFeatureWorker(BaseWorker):
    result_ready = pyqtSignal(dict)

    def run(self):
        try:
            # ... processing ...
            self.result_ready.emit({"key": "value"})
        except Exception as e:
            self.error.emit(str(e))

class MyFeatureTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        # Build layout; use self.tr() for all user-visible strings
        ...

    def _run_analysis(self):
        self.worker = MyFeatureWorker(...)
        self.worker.result_ready.connect(self._on_result)
        self.worker.error.connect(self._on_error)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.start()
```

**Naming conventions:**
- Tab classes: `PascalCaseTab` (e.g., `ExtractByIDTab`)
- Worker classes: `PascalCaseWorker`
- Files: `snake_case_tab.py`

## Key Utilities

| Utility | Usage |
|---------|-------|
| `utils/app_paths.py` | Always use `resource_path(...)` / `user_data_file(...)` for file paths — safe for both dev and PyInstaller builds |
| `utils/common_components.BaseTabWidget` | Base class for all tabs |
| `utils/common_components.BaseWorker` | Base class for background threads; built-in `finished`, `error`, `progress` signals |
| `config/settings.py` | `settings.get("window.width", 1100)` / `settings.set("key", value)` |
| `modules/fasta_processor.py` | `FASTAProcessor` and `FASTARecord` dataclass for sequence I/O |

## i18n

Wrap **all** user-visible strings in `self.tr("...")`. Do not use raw string literals in UI labels.

## External Tools

Paths resolved via `utils/app_paths.py`. Tool binaries live under `softwares/`:
- **BLAST**: `softwares/ncbi-blast-2.17.0+/bin/`
- **IQTree**: `softwares/iqtree-3.0.1-Windows/bin/`
- **TrimAl**: `softwares/trimAl_Windows_x86-64/`

`config.ini` `[BLAST] bin_dir` overrides the BLAST path at runtime.

## Styling

`styles.qss` is the primary stylesheet, loaded in `MainWindow._load_style()`. Do not hard-code colors; use QSS object names/classes instead. `resources/styles/modern_theme.qss` is the alternate theme variant.
