# BioSeqAnalyzer — Agent Instructions

PyQt6-based bioinformatics desktop app for sequence analysis. Keep this file minimal and actionable; link to [readme.txt](readme.txt) for user-facing feature descriptions.

## Verified Commands

Run from the repository root on Windows:

```bash
pip install -r requirements.txt
python main.py
py -m pytest tests/test_fasta_tools_tabs.py -q
```

Build the Windows one-file executable with Nuitka:

```powershell
.\scripts\build_windows_onefile.ps1 -Profile balanced
```

Notes:

- `tests/test_fasta_tools_tabs.py` is the current focused regression suite for FASTA Tools tabs.
- The pytest suite sets `QT_QPA_PLATFORM=offscreen`, so prefer pytest over ad hoc GUI automation for FASTA Tools regressions.
- `main.py` optionally shows a splash screen if `start_logo.png` exists in the repo root.

## Architecture

The app is a tab-based desktop UI. Each feature is implemented as an independent tab module and is typically opened lazily from `MainWindow`.

```text
main.py              -> QApplication bootstrap and optional splash screen
main_window.py       -> MainWindow, QTabWidget management, open_*_tab methods
menus.py             -> QAction wiring into MainWindow.open_*_tab methods
modules/             -> Feature tabs and supporting modules
utils/               -> Shared UI base classes, validation helpers, path utilities
config/settings.py   -> JSON-backed settings manager
config.ini           -> External tool path overrides
softwares/           -> Bundled BLAST, IQTree, TrimAl binaries
tests/               -> Pytest regression coverage
```

## Tab Conventions

- File-processing tabs should inherit `BaseTabWidget(..., "file")` from [utils/common_components.py](utils/common_components.py).
- Sequence-processing tabs should inherit `BaseTabWidget(..., "sequence")`.
- New tab files follow `snake_case_tab.py`; tab classes follow `PascalCaseTab`; worker classes follow `PascalCaseWorker`.
- New tabs must be wired in three places: the tab module under `modules/`, an `open_*_tab()` method in `main_window.py`, and a matching `QAction` in `menus.py`.
- For file-mode tabs, add `self.content_area.addStretch()` after the main controls so the shared operation log stays anchored at the bottom.
- Reuse `validate_input_path(...)` and `validate_output_path(...)` from `utils/common_components.py` for file validation instead of open-coded checks.

## Threading Guidance

- Use a `BaseWorker`/`DataWorker` subclass plus `QThread` for heavy CPU work, long-running external-tool calls, or network operations.
- Do not update Qt widgets directly from a worker `run()` method. Emit signals and update UI in the tab class.
- Small synchronous FASTA Tools operations may run on the main thread, but keep the method structured so it can be moved into a worker later if needed.

## FASTA / Bioinformatics Semantics

- Always use `FASTAProcessor` from [modules/fasta_processor.py](modules/fasta_processor.py) for FASTA IO unless there is a strong reason not to.
- `FASTAProcessor._add_record()` splits each FASTA header on the first space:
- `record.header` is the primary ID only.
- `record.description` is the remainder of the header line.
- `FASTAProcessor.save_file()` recombines them when writing output. This matters for any feature that matches, simplifies, extracts, or renames IDs.
- `FASTAProcessor.read_file()` tries UTF-8 first and falls back to Latin-1. Mirror this tolerance in related file readers when practical.

## Testing Guidance

- When changing FASTA Tools tabs, start with the narrowest relevant pytest selection, then rerun the full FASTA Tools suite:
- Focused: `py -m pytest tests/test_fasta_tools_tabs.py -k <tab_or_behavior> -q`
- Full suite: `py -m pytest tests/test_fasta_tools_tabs.py -q`
- Prefer fixture-driven tests over live network or interactive GUI checks.
- For NCBI-related code, keep default tests mock-based; live requests should stay optional.
- Assert both output artifacts and log/status text for file-mode tabs.

## Paths, Resources, and External Tools

- Prefer `utils/app_paths.py` helpers such as `resource_path(...)` and `user_data_file(...)` for runtime file lookup, especially for bundled resources and executables.
- External tool binaries live under `softwares/` by default:
- BLAST: `softwares/ncbi-blast-2.17.0+/bin/`
- IQTree: `softwares/iqtree-3.0.1-Windows/bin/`
- TrimAl: `softwares/trimAl_Windows_x86-64/`
- `config.ini` can override tool paths; preserve that behavior when modifying launcher code.

## UI and Styling

- `styles.qss` is the primary stylesheet; `resources/styles/modern_theme.qss` is the alternate theme.
- Do not hard-code one-off colors in Python when the styling belongs in QSS.
- When touching UI text, prefer wrapping new or edited user-visible strings in `self.tr(...)` even if older code in the repo is not fully converted yet.

## Dependencies

Core packages currently declared in [requirements.txt](requirements.txt):

- `PyQt6`
- `biopython`
- `numpy`, `scipy`, `matplotlib`, `pandas`
- `primer3-py`
- `logomaker`
- `phytreeviz`
