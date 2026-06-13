# BlastLocalTab Style Unification — Design

**Date:** 2026-06-13
**Goal:** Make `BlastLocalTab` visually consistent with all other file-mode tabs without affecting functionality.

## Decisions

1. **Inherit `BaseTabWidget("blast")`** — a new `tab_type` that skips both the Operation Log (file-mode) and sequence editors (sequence-mode), providing only: `content_area`, `status_label`, `help_btn`.
2. **Remove `_LOCAL_BLAST_STYLE`** — delete the 80+ line inline `setStyleSheet` from `BlastLocalTab.__init__()`.
3. **Extract reusable CSS to `styles.qss`** — move `actionRole="secondary"`, `mutedText`, `sectionTitle` property selectors so they're globally available.
4. **Drop `QTabWidget`/`QTabBar` rules** — these pollute MainWindow's tab bar.
5. **Keep `_DropLineEdit`** — shared `FileDropLineEdit` filters by extension, incompatible with BLAST database paths.

## Files Changed

| File | Changes |
|---|---|
| `styles.qss` | Add `QLabel[mutedText]`, `QLabel[sectionTitle]`, `QPushButton[actionRole="secondary"]` |
| `blast_local_tab.py` | `BlastLocalTab(QWidget)` → `BlastLocalTab(BaseTabWidget)`; remove `setStyleSheet`; wire `show_status`; remove inline help buttons |
| `main_window.py` | Minor: `status_callback` may be simplified |
