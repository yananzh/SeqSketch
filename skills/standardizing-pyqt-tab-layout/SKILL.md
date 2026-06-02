---
name: standardizing-pyqt-tab-layout
description: Use when creating or refactoring BioSeqAnalyzer PyQt tabs and they should follow the DNA Analysis layout pattern for sectioning, bottom action placement, horizontal form rows, and consistent control naming.
---

# Standardizing PyQt Tab Layout

## Overview

Use `BaseTabWidget` as the default skeleton and keep tab layouts predictable. Users should be able to find input, parameters, output, primary actions, and help in roughly the same place across tabs without relearning each screen.

## When to Use

- New tab modules under `modules/`
- Refactoring tabs with ad hoc spacing or control placement
- Normalizing a file-mode tab to match the stronger DNA Analysis sequence-tab rhythm
- Naming new controls that already exist elsewhere in similar form

Do not use this to force unnecessary boxes or extra rows onto a very small tab with only one input and one action.

## Layout Order

Keep this top-to-bottom order unless the feature has a strong reason to break it:

1. Input section
2. Parameter section
3. Output or Results section
4. Primary actions at the bottom-left
5. Help at the bottom-right
6. Shared status and log area anchored at the bottom for file-mode tabs

When a tab has two or more logical blocks, show that structure clearly. Use lightweight section labels or `QGroupBox` containers for `Input`, `Parameters`, `Output`, `Results`, or `Run Summary` rather than one long undifferentiated column.

For `BaseTabWidget(..., "sequence")`, keep the base input and output sections unless the feature genuinely needs a custom shell. Insert one clearly defined parameter section between them, keep the base `Run` and `Clear` controls as the lower-left action cluster, and leave `help_btn` in the base status bar at the lower right.

## Quick Reference

| Topic | Guidance |
| --- | --- |
| Sectioning | Prefer clear sections such as `Input`, `Parameters`, and `Output` when the tab has more than one logical block. |
| Form rows | Put `QLabel` and single-line controls such as `QLineEdit`, `QComboBox`, and `QSpinBox` in the same `QHBoxLayout`. Avoid stacking the label above the field unless the control is genuinely multi-line. |
| Alignment | Keep label widths aligned within the same section so rows scan vertically. A practical default is `120` to `140` px for row labels in standard parameter sections. Give controls a sensible minimum width, then end the row with `addStretch()` to keep content left-aligned. |
| Primary action | Keep the main `Run` or `Start` button at the lower left. Put secondary actions such as `Clear` immediately to its right. |
| Help action | Keep `help_btn` at the lower right, separate from the primary action cluster. In `BaseTabWidget`, this normally means the bottom status bar, not the same row as `Run` and `Clear`. |
| Naming | Reuse common names where the function is the same: `run_btn`, `start_btn`, `clear_btn`, `help_btn`, `upload_btn`, `export_btn`, `copy_btn`, `input_text`, `output_text`, `input_file_edit`, `output_file_edit`, `output_dir_edit`. |
| Status updates | Prefer shared helpers such as `show_status(...)` instead of writing to `status_label` directly throughout the tab. |
| Manual text editors | If a tab creates its own `QTextEdit`, call `apply_sequence_editor_style(...)` so borders, radius, and viewport styling stay consistent. |
| File-mode tabs | After the main controls, call `self.content_area.addStretch()` so the shared log area remains anchored at the bottom instead of floating upward. |
| Plot tabs | A canvas can replace text output, but preserve the same section order. Put the navigation toolbar directly above the canvas. |

## Naming Rule For Equivalent Controls

If two tabs expose the same concept, prefer the same code name and similar visible label text.

Use stable suffixes for common widget types:

- `*_edit` for `QLineEdit`
- `*_box` for `QComboBox` and `QSpinBox` in this codebase's existing style
- `*_text` for `QTextEdit`
- `*_btn` for `QPushButton`

- File chooser for the main source input: `input_file_edit` with label `Input File:`
- Output directory chooser: `output_dir_edit` with label `Output Directory:`
- Primary one-shot action: `run_btn` with text `Run`
- Primary long-running workflow action: `start_btn` with text `Start`

Do not mix `Run`, `Start`, `Analyze`, and `Process` for the same kind of action unless the workflow semantics are genuinely different.

## Example Pattern

```python
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QGroupBox, QVBoxLayout

params_group = QGroupBox("Parameters")
params_layout = QVBoxLayout(params_group)

threshold_row = QHBoxLayout()
threshold_label = QLabel("Identity Threshold:")
threshold_label.setMinimumWidth(140)
self.threshold_edit = QLineEdit()
self.threshold_edit.setMinimumWidth(180)
threshold_row.addWidget(threshold_label)
threshold_row.addWidget(self.threshold_edit)
threshold_row.addStretch()
params_layout.addLayout(threshold_row)

actions_row = QHBoxLayout()
self.run_btn = QPushButton("Run")
self.clear_btn = QPushButton("Clear")
actions_row.addWidget(self.run_btn)
actions_row.addWidget(self.clear_btn)
actions_row.addStretch()

self.content_area.addWidget(params_group)
self.content_area.addLayout(actions_row)
self.content_area.addStretch()
```

If the tab already inherits the sequence shell from `BaseTabWidget`, adapt the same idea by inserting one dedicated parameter layout between the base input and output blocks instead of rebuilding the whole page or scattering multiple anonymous `insertLayout(...)` calls.

## Common Mistakes

- Adding controls in a single long column without visible Input, Parameters, and Output grouping.
- Placing `Help` next to the primary execute button instead of keeping it at the lower right.
- Stacking `QLabel` above a `QLineEdit` or `QComboBox` for routine one-line settings.
- Using different names for the same role, such as `file_edit`, `input_path_edit`, and `source_path_box` in neighboring tabs.
- Repeatedly relying on brittle layout indices like `insertLayout(1, ...)` for every new row. If a sequence tab must insert content into the base shell, build one dedicated parameter section and insert it once.
- Leaving unused base widgets visible as empty space instead of hiding or repurposing them deliberately.
- Mixing direct `status_label.setText(...)` calls with helper-based status updates, producing inconsistent behavior.
- Using noticeably different editor heights or spacing in tabs that otherwise perform the same kind of work.

## Practical Defaults

- Sequence tabs: keep input and output editors visually balanced unless output is naturally report-heavy.
- File tabs: keep file pickers near the top, parameters in the middle, and logs at the bottom.
- Use placeholder text and short hints to explain expected input format close to the input widget.
- Wrap new user-visible strings with `self.tr(...)` when touching UI text.
