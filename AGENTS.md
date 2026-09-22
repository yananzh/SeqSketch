# SeqSketch — Agent Instructions

PyQt6-based bioinformatics desktop app for sequence analysis. Keep this file minimal and actionable; link to [README.MD](README.MD) for user-facing feature descriptions.

## Verified Commands

Run from the repository root on Windows:

```bash
pip install -r requirements.txt
pip install -r dev-requirements.txt   # pytest, pytest-timeout, ruff
.\scripts\fetch_softwares.ps1         # external tool binaries (gitignored, ~80 MB download)
python main.py
py -m pytest tests/test_dna_analysis_tabs.py -q
py -m pytest tests/test_fasta_tools_tabs.py -q
py -m pytest tests/test_tool_paths.py -q   # platform tool resolution
py -m pytest -q                       # full suite (auto-timeout 60s per test)
ruff check .                          # lint
```

CI (`.github/workflows/ci.yml`) runs `ruff check .` plus the suite on `windows-latest`
and `macos-15`. It does **not** fetch the tools: tests that shell out to them mock the
launcher, and the two that need a real bundle skip themselves.

Build the Windows portable onedir distribution with PyInstaller:

```powershell
.\scripts\build_onedir.ps1
```

The output `dist/SeqSketch/` is a self-contained portable folder — copy it anywhere.

Notes:

- `tests/conftest.py` provides the shared `qapp` fixture and sets `QT_QPA_PLATFORM=offscreen`.
- `tests/test_fasta_tools_tabs.py` covers the file-mode FASTA Tools tabs.
- `tests/test_dna_analysis_tabs.py` covers sequence-mode DNA tabs plus `MainWindow` tab reuse and menu wiring.
- `pyproject.toml` configures `pytest` (timeout=60s) and `ruff` (line-length=100, target=py310).
- Prefer pytest over ad hoc GUI automation for FASTA Tools regressions.
- `main.py` optionally shows a splash screen if `start_logo.png` exists in the repo root.

## Scoped Instructions

- Keep this file short. Put tab-editing specifics in [.github/instructions/pyqt-tabs.instructions.md](.github/instructions/pyqt-tabs.instructions.md).
- Put bundled-resource, per-user runtime file, and external-tool launcher specifics in [.github/instructions/runtime-paths.instructions.md](.github/instructions/runtime-paths.instructions.md).
- Past feature design docs (rationale, alternatives considered) live under [docs/superpowers/specs/](docs/superpowers/specs/) and [docs/superpowers/plans/](docs/superpowers/plans/); check there before re-deciding an already-settled design question.

## Architecture

The app is a tab-based desktop UI. Each feature is implemented as an independent tab module and is typically opened lazily from `MainWindow`.

```text
main.py              -> QApplication bootstrap and optional splash screen
main_window.py       -> MainWindow, QTabWidget management, open_*_tab methods
menus.py             -> QAction wiring into MainWindow.open_*_tab methods
modules/             -> Feature tabs and supporting modules
utils/               -> Shared UI base classes, validation helpers, path utilities, example-data loader
config/settings.py   -> JSON-backed settings manager (planned, currently unused)
config.ini           -> External tool path overrides
softwares/           -> External tool binaries per platform (gitignored; scripts/fetch_softwares.ps1)
examples/            -> Bundled read-only teaching datasets (phylo/, labs/) resolved via resource_path
tests/               -> Pytest regression coverage
```

## Tab Conventions

- File-processing tabs should inherit `BaseTabWidget(..., "file")` from [utils/common_components.py](utils/common_components.py).
- Sequence-processing tabs should inherit `BaseTabWidget(..., "sequence")`.
- New tab files follow `snake_case_tab.py`; tab classes follow `PascalCaseTab`; worker classes follow `PascalCaseWorker`.
- New tabs must be wired in three places: the tab module under `modules/`, an `open_*_tab()` method in `main_window.py`, and a matching `QAction` in `menus.py`.
- For multi-step orchestration tabs (a tab that drives several existing tools end-to-end, e.g. `modules/one_step_multigenephy_tab.py`), it's fine to split the feature into sibling `_io.py` / `_models.py` / `_workflow.py` / `_tab.py` modules instead of one file. See [docs/superpowers/specs/2026-05-31-one-step-multigenephy-design.md](docs/superpowers/specs/2026-05-31-one-step-multigenephy-design.md) for the design rationale.
- In `main_window.py`, preserve the nearby single-instance vs multi-instance behavior for each feature; do not normalize tab reuse patterns unless the task explicitly asks for it.
- For file-mode tabs, add `self.content_area.addStretch()` after the main controls so the shared operation log stays anchored at the bottom.
- Reuse `validate_input_path(...)` and `validate_output_path(...)` from `utils/common_components.py` for file validation instead of open-coded checks.
- **MAFFT's single-file mode is `BaseTabWidget(..., "sequence")`** — input is pasted into `self.input_text`, not a file path. Only its batch sub-mode uses a file list. Do not wire MAFFT Example buttons as file-mode.

## Example Data (Teaching)

- `examples/phylo/` holds a read-only 8-species cytb dataset (CDS, protein, aligned variants, Newick tree, README) used by the "Example" buttons on the 7 core teaching-chain tabs (FASTA Statistics, Translate, Physicochemical, MAFFT, trimAl, IQ-TREE, Tree Visualization).
- `utils/example_data.py` is the **only** module that knows where examples live: `example_path(*parts)` (read-only bundled source), `stage_example(*parts)` (copies to `user_data_dir()/example_work/` for file-mode tabs so outputs can write), `load_example_text(*parts)` (reads text for sequence-mode tabs). Use these instead of open-coded `resource_path("examples", ...)` calls in tabs.
- When adding an "Example" button to a new tab, follow the existing pattern: load → empty-check with `QMessageBox.information` → fill the tab's specific input control → `self.show_status("Example loaded: ...")`. File-mode tabs stage a writable copy; sequence-mode tabs fill `input_text` directly.
- `examples/` is bundled via `SeqSketch.spec` `datas` (`('examples', 'examples')`); any new example subfolder is picked up automatically.

## Threading Guidance

- Use a `BaseWorker` subclass plus `QThread` for heavy CPU work, long-running external-tool calls, or network operations.
- Do not update Qt widgets directly from a worker `run()` method. Emit signals and update UI in the tab class.
- Small synchronous FASTA Tools operations may run on the main thread, but keep the method structured so it can be moved into a worker later if needed.

## Reproducibility (run_log.txt)

- Every external-tool run (MAFFT, MUSCLE, IQ-TREE, trimAl, BLAST, makeblastdb) must append a provenance block — tool, probed version, full argv (`list2cmdline`), timestamp — to `run_log.txt` in the output directory.
- Use `utils/run_provenance.py`: `record_tool_run(output_dir, tool, exe, cmd, ...)` in the worker thread after a successful run (never on the GUI thread — version probing spawns a subprocess, cached per exe).
- Single-file modes record one entry per run into the output file's directory; batch modes record one entry per batch run (with a note listing the input count) into the batch output dir; per-task tools like trimAl record one entry per task.
- Version probing is best-effort and cached; it never raises and reports "unknown" on failure. Keep data files machine-clean — provenance goes to `run_log.txt`, not into TSV/FASTA outputs.
- The One Step pipeline records centrally in `_run_command()` and mirrors the same data into `run_manifest.json` (`commands`, `tool_versions`) and the HTML report.

## FASTA / Bioinformatics Semantics

- Always use `FASTAProcessor` from [modules/fasta_processor.py](modules/fasta_processor.py) for FASTA IO unless there is a strong reason not to.
- In-memory FASTA (pasted text) goes through `FASTAProcessor.parse_text()` or the helpers `parse_fasta_tuples()` / `parse_fasta_dict()`. Do not add a local `_parse_fasta`.
- `FASTAProcessor._add_record()` splits each FASTA header on the first space:
- `record.header` is the primary ID only.
- `record.description` is the remainder of the header line.
- `FASTAProcessor.save_file()` recombines them when writing output. This matters for any feature that matches, simplifies, extracts, or renames IDs.
- `FASTAProcessor.read_file()` tries UTF-8 first and falls back to Latin-1, then calls `parse_text()`. Mirror this tolerance in related file readers when practical.
- `validate_file(sequence_type="nucleotide"|"protein"|"auto")` distinguishes alphabets. Default is nucleotide. `auto` accepts an all-nucleotide or all-protein file and rejects mixed types. Neither alphabet includes gaps.
- App version is `APP_VERSION` in [utils/app_version.py](utils/app_version.py). Do not put `__version__` or eager tab imports in [modules/__init__.py](modules/__init__.py).

## Testing Guidance

- When changing file-mode FASTA Tools tabs, start with the narrowest relevant pytest selection, then rerun the full FASTA Tools suite:
- Focused FASTA Tools: `py -m pytest tests/test_fasta_tools_tabs.py -k <tab_or_behavior> -q`
- Full FASTA Tools: `py -m pytest tests/test_fasta_tools_tabs.py -q`
- Focused DNA analysis / window wiring: `py -m pytest tests/test_dna_analysis_tabs.py -k <tab_or_behavior> -q`
- Full DNA analysis / window wiring: `py -m pytest tests/test_dna_analysis_tabs.py -q`
- Example data loaders / per-tab Example buttons: `py -m pytest tests/test_example_data.py -q`
- Prefer fixture-driven tests over live network or interactive GUI checks.
- For NCBI-related code, keep default tests mock-based; live requests should stay optional.
- Assert both output artifacts and log/status text for file-mode tabs.

## Paths, Resources, and External Tools

- Prefer `utils/app_paths.py` helpers such as `resource_path(...)` and `user_data_file(...)` for runtime file lookup, especially for bundled resources and executables.
- Use `user_data_file(...)` / `user_data_dir(...)` for writable settings and user data; avoid writing mutable runtime state into the repo root or bundled resource tree.
- `modules/blast_config.py` still reads the repo-root `config.ini` as a legacy fallback, then persists the resolved value into the per-user config file. Preserve equivalent migration behavior if you move or add persisted settings.
- If you touch `main.py`, `main_window.py`, or launcher tabs that still derive paths from `__file__`, prefer moving toward `resource_path(...)` instead of copying legacy path-building patterns into new code.
- External tool binaries live under the per-platform `softwares/` folder:
- Windows: `softwares/windows/`, macOS: `softwares/Mac/`
- e.g. `windows/ncbi-blast-2.17.0+/bin/blastn.exe`, `Mac/iqtree-3.1.3-macOS/bin/iqtree3`
- **Resolve them through `utils/tool_paths.py`** (`mafft_launcher()`, `trimal_executable()`,
  `iqtree_executable()`, `muscle_executable()`) — it owns the per-platform folder and
  executable names. Never hard-code a bundle folder or `.exe` suffix in a tab; tool folder
  names are version-numbered and differ per platform (`tests/test_tool_paths.py` enforces this).
- `config.ini` can override tool paths (empty = auto-detect the bundled copy); preserve that
  behavior when modifying launcher code.

## Licensing (do not regress)

- Every bundled tool must ship its licence text **inside its own folder** under
  `softwares/<platform>/` — the conditions have to travel with the download. `tests/test_license_compliance.py`
  enforces this plus the content markers that prove the text is the real licence.
- Tool versions and licences are documented in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)
  (repo root, also bundled into the packaged app). Update it when a tool is added or upgraded.
- Licence texts for the bundled Python packages live in `third_party_licenses/` and are regenerated with
  `python scripts/collect_licenses.py` (`--check` verifies them). The directory is generated — do not
  hand-edit it.
- **The project is licensed `GPL-3.0`** ([LICENSE](LICENSE)), because PyQt6 is `GPL-3.0-only`. Do not
  introduce a permissive project-licence claim in `README.MD`, `version_info.txt`, or the About
  dialog; the section `## 许可与来源` records the status deliberately.
- Take licences from the **shipped text**, not from PyPI classifiers — they disagree in
  practice (e.g. `toytree` and `sangerseq-viewer` are listed as GPLv3 but ship BSD-3 and MIT).

## UI and Styling

- `styles.qss` is the primary stylesheet; `resources/styles/modern_theme.qss` is the alternate theme.
- Do not hard-code one-off colors in Python when the styling belongs in QSS.
- The UI is English-only by decision — i18n was dropped (2026-08). Do not wrap user-visible strings in `self.tr(...)`; write plain English literals. Never mix CJK characters into UI text, status messages, or help dialogs.

## Dependencies

Core packages currently declared in [requirements.txt](requirements.txt):

- `PyQt6`
- `biopython`
- `numpy`, `matplotlib`, `pandas`
- `primer3-py`
- `logomaker`
