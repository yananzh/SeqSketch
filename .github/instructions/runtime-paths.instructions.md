---
description: "Use when editing runtime path lookup, bundled external-tool launchers, or per-user config/data files. Covers resource_path/user_data_file, legacy config migration, and subprocess/thread conventions for packaged Windows builds."
name: "Runtime Paths And External Tools"
applyTo: main.py, main_window.py, utils/app_paths.py, modules/blast_config.py, modules/blast_make_db_dialog.py, modules/blast_run_dialog.py, modules/iqtree_tab.py, modules/multiple_sequence_alignment_tab.py, modules/partition_concat_tab.py, modules/trimal_tab.py, modules/tree_visualization_tab.py, modules/favorites_manager.py
---

# Runtime Paths And External Tools

- Use [AGENTS.md](../AGENTS.md) for repo-wide architecture, commands, and testing guidance. Keep this file focused on runtime path and launcher work.
- Prefer `resource_path(...)` from [utils/app_paths.py](../utils/app_paths.py) for bundled executables, QSS, icons, splash images, and other packaged resources. Some older modules still derive `_HERE` from `__file__`; treat those patterns as legacy unless the task is explicitly about maintaining them.
- Use `user_data_file(...)` / `user_data_dir(...)` for writable runtime state such as `config.ini`, bookmarks, and user-generated metadata. Do not write mutable state into the repo root or bundled resource tree.
- Preserve legacy config migration when it exists. [modules/blast_config.py](../modules/blast_config.py) reads both the per-user file and the repo-root `config.ini`; if you add similar settings, keep older installs working and persist the resolved value back to the user-data location.
- Long-running external tools must stay off the UI thread in `QThread` or a shared worker base. Emit progress or log signals back to the tab instead of touching widgets inside worker code.
- When spawning Windows command-line tools with `subprocess.Popen`, pass `creationflags=subprocess.CREATE_NO_WINDOW` where appropriate so bundled executables do not flash a console window.
- Surface enough stdout/stderr or per-file log text for users and tests to diagnose failures; avoid swallowing subprocess errors behind generic dialogs.
- Keep tests and validation mock-friendly: default automation should not depend on live NCBI access or manually installed binaries when a config/path seam can be injected instead.