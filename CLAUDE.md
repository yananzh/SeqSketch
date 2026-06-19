# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

```bash
pip install -r requirements.txt
pip install -r dev-requirements.txt   # pytest, pytest-timeout, ruff
python main.py
py -m pytest -q                       # full suite (auto-timeout 60s per test)
ruff check .                          # lint
```

Build Windows portable distribution:
```powershell
.\scripts\build_onedir.ps1
```
Output: `dist/SeqSketch/` — self-contained portable folder.

## Project Overview

**SeqSketch** — PyQt6-based bioinformatics desktop app for sequence analysis. Tab-based UI with features spanning FASTA processing, DNA/RNA analysis, protein analysis, alignment, BLAST, primer design, phylogenetics, and Sanger sequencing.

## Architecture

```
main.py           → QApplication bootstrap + optional splash screen
main_window.py    → MainWindow, QTabWidget management, open_*_tab methods
menus.py          → QAction wiring into MainWindow.open_*_tab methods
modules/          → Feature tabs (~40), each independent
utils/            → BaseTabWidget, BaseWorker/DataWorker, path helpers, validation
config/settings.py → JSON-backed settings manager
config.ini         → External tool path overrides
softwares/         → Bundled BLAST, IQTree, TrimAl binaries
resources/         → Icons and language packs
styles.qss         → Primary QSS stylesheet
tests/             → Pytest regression with QT_QPA_PLATFORM=offscreen
```

## Adding or Modifying a Tab

1. Create module under `modules/` using `snake_case_tab.py`, class `PascalCaseTab`
2. File-processing tabs inherit `BaseTabWidget(..., "file")`; sequence tabs inherit `BaseTabWidget(..., "sequence")`
3. Wire an `open_*_tab()` method in `main_window.py` (preserve nearby single-instance vs multi-instance reuse patterns)
4. Wire a `QAction` in `menus.py`
5. For file-mode tabs: add `self.content_area.addStretch()` after main controls to keep the log anchored at bottom
6. Use `validate_input_path()` / `validate_output_path()` from `utils/common_components.py` for file validation
7. Use `BaseWorker`/`DataWorker` + `QThread` for heavy CPU, external-tool, or network work — never touch widgets from `run()`, emit signals instead

## FASTA Semantics

- Always use `FASTAProcessor` from `modules/fasta_processor.py` for FASTA I/O
- `_add_record()` splits headers on first space: `header` = primary ID, `description` = remainder
- `save_file()` recombines them on write — this matters for any ID-matching, extraction, or renaming feature
- `read_file()` tries UTF-8 first, falls back to Latin-1

## Paths and External Tools

- `utils/app_paths.py`: `resource_path(...)` for bundled resources, `user_data_file(...)` / `user_data_dir(...)` for writable runtime state
- External tools live under `softwares/` by default; `config.ini` can override. Preserve that override behavior.
- `modules/blast_config.py` reads both repo-root `config.ini` and per-user config as legacy migration

## Testing

- Two main suites: `tests/test_dna_analysis_tabs.py` (sequence-mode + window wiring) and `tests/test_fasta_tools_tabs.py` (file-mode FASTA Tools)
- Focused runs: `py -m pytest tests/test_fasta_tools_tabs.py -k <tab_name> -q`
- File-mode tabs: assert output artifacts AND log/status text
- Sequence-mode tabs: assert editor styling, menu labels, tab reuse behavior
- Keep NCBI-related tests mock-based; live requests optional

## Styling

- Primary: `styles.qss`; alternate: `resources/styles/modern_theme.qss`
- For sequence `QTextEdit` widgets, use `apply_sequence_editor_style(...)` from `utils/common_components.py`
- Don't hardcode colors in Python when QSS is the right place

## Detailed Instructions

See [AGENTS.md](AGENTS.md) for comprehensive guidance on threading, runtime paths, tab conventions, and more. See `.github/instructions/pyqt-tabs.instructions.md` for tab-editing specifics and `.github/instructions/runtime-paths.instructions.md` for bundled-resource and external-tool launcher specifics.
