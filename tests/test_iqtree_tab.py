"""Tests for the ML Tree Construction (IQ-TREE) tab."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QPushButton

from modules.iqtree_tab import IqTreeTab


def test_example_button_in_alignment_row_left_of_browse(qapp):
    tab = IqTreeTab()

    # Example is no longer in the status bar
    assert tab.status_layout.indexOf(tab._example_btn) == -1

    # Example shares the alignment row with Browse, positioned to its left
    input_group_layout = tab._input_edit.parent().layout()
    alignment_row = None
    for i in range(input_group_layout.count()):
        row = input_group_layout.itemAt(i).layout()
        if row is not None and row.indexOf(tab._input_edit) >= 0:
            alignment_row = row
            break
    assert alignment_row is not None
    buttons = [
        (widget, widget.text())
        for i in range(alignment_row.count())
        if isinstance((widget := alignment_row.itemAt(i).widget()), QPushButton)
    ]
    example_idx = next(i for i, (_, t) in enumerate(buttons) if t == "Example")
    browse_idx = next(i for i, (_, t) in enumerate(buttons) if t == "Browse")
    assert example_idx < browse_idx


def test_outgroup_added_to_command(qapp):
    tab = IqTreeTab()
    tab._input_edit.setText("C:/x/aln.fasta")
    tab._outgroup_combo.setCurrentText("taxonA,taxonB")

    cmd = tab._build_cmd()

    assert "-o" in cmd
    assert cmd[cmd.index("-o") + 1] == "taxonA,taxonB"


def test_outgroup_omitted_when_blank(qapp):
    tab = IqTreeTab()
    tab._input_edit.setText("C:/x/aln.fasta")

    cmd = tab._build_cmd()

    assert "-o" not in cmd


def test_outgroup_dropdown_populated_from_input_file(qapp, tmp_path):
    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(
        ">taxonA\nATGC\n>taxonB\nATGC\n>taxonC\nATTC\n", encoding="utf-8"
    )

    tab = IqTreeTab()
    tab._input_edit.setText(str(aln_file))

    # textChanged fires synchronously on setText -> dropdown is populated
    items = [tab._outgroup_combo.itemText(i) for i in range(tab._outgroup_combo.count())]
    assert items == ["taxonA", "taxonB", "taxonC"]


def test_outgroup_dropdown_preserves_typed_value_when_refreshed(qapp, tmp_path):
    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(">taxonA\nATGC\n>taxonB\nATGC\n", encoding="utf-8")

    tab = IqTreeTab()
    tab._input_edit.setText(str(aln_file))
    tab._outgroup_combo.setCurrentText("taxonB")

    # re-trigger refresh (e.g. file changed) — selection survives
    tab._refresh_outgroup_taxa()

    assert tab._outgroup_combo.currentText() == "taxonB"


def test_result_folder_button_exists(qapp):
    tab = IqTreeTab()

    assert tab.open_output_btn.text() == "Result Folder"


def test_open_output_folder_uses_outdir_or_input_dir(qapp, monkeypatch, tmp_path):
    tab = IqTreeTab()
    opened = []
    monkeypatch.setattr(
        "modules.iqtree_tab.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )

    # no outdir and no input file -> status message
    tab._open_output_folder()
    assert tab.status_label.text() == "No output folder selected yet."

    # outdir set -> opens it
    outdir = tmp_path / "out"
    outdir.mkdir()
    tab._outdir_edit.setText(str(outdir))
    tab._open_output_folder()
    assert opened == [QUrl.fromLocalFile(str(outdir)).toString()]

    # blank outdir -> falls back to the input file's directory
    tab._outdir_edit.clear()
    aln = tmp_path / "aln.fasta"
    aln.write_text(">a\nATGC\n", encoding="utf-8")
    tab._input_edit.setText(str(aln))
    tab._open_output_folder()
    assert opened[-1] == QUrl.fromLocalFile(str(tmp_path)).toString()


def test_log_output_files_lists_existing_outputs(qapp, tmp_path):
    tab = IqTreeTab()
    (tmp_path / "myrun.treefile").write_text("(a);", encoding="utf-8")
    (tmp_path / "myrun.iqtree").write_text("report", encoding="utf-8")
    tab._last_treefile = str(tmp_path / "myrun.treefile")

    tab._log_output_files()

    log = tab.log_area.toPlainText()
    assert "Output files" in log
    assert "myrun.treefile" in log
    assert "myrun.iqtree" in log
    assert "best-scoring ML tree" in log


def test_sh_alrt_checkbox_in_bootstrap_row(qapp):
    tab = IqTreeTab()
    param_layout = tab._bootstrap_spin.parent().layout()

    boot_row = None
    for i in range(param_layout.count()):
        row = param_layout.itemAt(i).layout()
        if row is not None and row.indexOf(tab._bootstrap_spin) >= 0:
            boot_row = row
            break
    assert boot_row is not None
    assert boot_row.indexOf(tab._alrt_check) >= 0
    assert boot_row.indexOf(tab._alrt_spin) >= 0


def test_outgroup_row_above_output_directory(qapp):
    tab = IqTreeTab()
    param_layout = tab._outdir_edit.parent().layout()

    indexes = {}
    for i in range(param_layout.count()):
        row = param_layout.itemAt(i).layout()
        if row is None:
            continue
        for widget in (tab._outgroup_combo, tab._outdir_edit):
            if row.indexOf(widget) >= 0:
                indexes[widget] = i
    assert tab._outgroup_combo in indexes and tab._outdir_edit in indexes
    assert indexes[tab._outgroup_combo] < indexes[tab._outdir_edit]


def test_threads_max_equals_cpu_count(qapp):
    tab = IqTreeTab()

    assert tab._threads_spin.maximum() == max(os.cpu_count() or 1, 1)


def test_row1_param_boxes_have_same_width(qapp):
    tab = IqTreeTab()
    widths = {
        tab._seqtype_combo.minimumWidth(),
        tab._threads_spin.minimumWidth(),
        tab._model_edit.minimumWidth(),
        tab._prefix_edit.minimumWidth(),
    }

    assert widths == {90}
