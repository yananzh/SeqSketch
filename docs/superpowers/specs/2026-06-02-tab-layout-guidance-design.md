# PyQt Tab Layout Guidance Skill Design

## Summary

Add a repo-local skill at `skills/standardizing-pyqt-tab-layout/SKILL.md` to standardize PyQt tab layout decisions across BioSeqAnalyzer.

The guidance should follow the visual rhythm already established by `BaseTabWidget` and the stronger DNA Analysis sequence tabs, while making several expectations explicit that current code does not always enforce:

- prefer clear sections such as Input, Parameters, and Output when the tab has more than one logical block
- keep the primary `Run` or `Start` action at the lower left
- keep `Help` at the lower right
- keep labels and single-line editors in the same horizontal row when possible
- keep equivalent widgets named consistently across tabs

## Baseline Failure Observed

A baseline subagent pass without this skill produced only generic layout advice. It mentioned parameter grouping and button order in broad terms, but it did not naturally converge on:

- explicit sectioning rules
- the required `Help` bottom-right and `Run` or `Start` bottom-left placement
- horizontal label-plus-line-edit rows as a default form pattern
- naming consistency for equivalent controls

It also surfaced a few existing code smells that the skill should warn against:

- brittle `insertLayout(1, ...)` placement
- direct `status_label.setText(...)` updates instead of a shared helper
- inconsistent editor heights and hidden/unused base widgets

## Goals

- Give future tab work a concrete, reusable layout checklist.
- Preserve the repo's existing `BaseTabWidget` conventions instead of inventing a new page structure.
- Cover both sequence-mode and file-mode tabs.
- Document naming conventions for common controls so related tabs read similarly in code and in the UI.

## Non-Goals

- Refactoring all existing tabs now.
- Enforcing layout rules through a new framework layer.
- Replacing existing feature-specific UX where a different output surface is justified, such as plots or multi-panel viewers.

## Skill Structure

The skill should contain:

1. A short overview explaining the consistency goal.
2. When-to-use bullets tuned to tab creation and refactoring.
3. A concrete layout order section.
4. A quick-reference table for sectioning, row layout, button placement, naming, and spacing.
5. One small Python example showing a labeled row and bottom action alignment.
6. Common mistakes rooted in the baseline failures.

## Content Decisions

- Recommend `Run` for normal one-shot processing tabs and `Start` for long-running workflow tabs; do not mix terms casually.
- Keep `Help` separate from primary actions so it remains discoverable and does not compete with execution controls.
- Recommend aligned label widths within a section so parameter rows scan cleanly.
- Remind authors to use `apply_sequence_editor_style(...)` for manual `QTextEdit` instances and `show_status(...)` for status updates.
- For file tabs, explicitly mention `self.content_area.addStretch()` after the main controls so the shared log area stays anchored at the bottom.

## Files

- New: `skills/standardizing-pyqt-tab-layout/SKILL.md`
