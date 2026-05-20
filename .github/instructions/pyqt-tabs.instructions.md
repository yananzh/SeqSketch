---
description: "Use when editing PyQt tab modules, tab wiring in main_window.py or menus.py, shared tab widgets, or pytest tab regression files. Covers BaseTabWidget patterns, sequence editor styling, and focused GUI test expectations."
name: "PyQt Tab Workflow"
applyTo: modules/*_tab.py, tests/test_*_tabs.py, utils/common_components.py, main_window.py, menus.py
---

# PyQt Tab Workflow

- Use [AGENTS.md](../AGENTS.md) for repo-wide architecture, commands, and FASTA semantics. Keep this file focused on tab and tab-test work.
- Prefer `BaseTabWidget` from [utils/common_components.py](../utils/common_components.py): file-processing tabs use `BaseTabWidget(..., "file")`; sequence-processing tabs use `BaseTabWidget(..., "sequence")`.
- For sequence `QTextEdit` widgets, use `apply_sequence_editor_style(...)` instead of ad hoc stylesheet snippets. Existing tests assert the `sequenceEditorStyled` property, direct border declarations, and `editor.viewport().setStyleSheet("background: transparent;")`.
- For file-mode tabs, add `self.content_area.addStretch()` after the main controls so the shared log area stays anchored near the bottom.
- Reuse `validate_input_path(...)` and `validate_output_path(...)` from [utils/common_components.py](../utils/common_components.py) instead of open-coded validation.
- When adding or renaming a tab, update the tab module under `modules/`, the matching `open_*_tab()` method in [main_window.py](../main_window.py), and the corresponding `QAction` in [menus.py](../menus.py) together.
- Follow the nearby `MainWindow` behavior for tab reuse. Some features reuse a single tab instance, while others intentionally open a fresh tab each time.
- Prefer wrapping new or edited user-visible strings in `self.tr(...)`, even if the surrounding file still has older untranslated literals.
- For tests under `tests/test_*_tabs.py`, keep `QT_QPA_PLATFORM=offscreen`, prefer focused pytest selections first, and assert the user-visible behavior that matches the tab type:
- File-mode tabs: output artifacts plus log/status text.
- Sequence-mode tabs and window wiring: editor styling, menu labels, and single-instance tab behavior where applicable.