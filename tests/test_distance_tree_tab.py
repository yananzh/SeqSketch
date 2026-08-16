"""Tests for the Distance Tree Construction tab."""

import math
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Bio.Align import MultipleSeqAlignment
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from PyQt6.QtWidgets import QPushButton

from modules.distance_tree_tab import (
    _DNA_MODELS,
    DistanceTreeTab,
    _DistanceTreeWorker,
    _dna_distance_matrix,
)


def _aln(*seqs):
    return MultipleSeqAlignment(
        [SeqRecord(Seq(s), id=f"t{i}") for i, s in enumerate(seqs)]
    )


# ── DNA models ────────────────────────────────────────────────────────────


def test_dna_models_include_jc69_k80_and_drop_blastn():
    datas = [data for _, data in _DNA_MODELS]

    assert "blastn" not in datas
    assert "jc69" in datas
    assert "k80" in datas


def test_jc69_distance_matches_formula():
    # 1 of 4 sites differ -> p = 0.25 -> d = -3/4 * ln(1 - 4/3 * 0.25)
    dm = _dna_distance_matrix(_aln("ATGC", "ATCC"), "jc69")
    expected = -0.75 * math.log(2.0 / 3.0)

    assert abs(dm[0][1] - expected) < 1e-9


def test_k80_separates_transitions_and_transversions():
    # one transition (A->G) and one transversion (A->C)
    transition = _dna_distance_matrix(_aln("ATGC", "GTGC"), "k80")
    transversion = _dna_distance_matrix(_aln("ATGC", "CTGC"), "k80")

    exp_trans = -0.5 * math.log(0.5)
    exp_transv = -0.5 * math.log(0.75) - 0.25 * math.log(0.5)

    assert abs(transition[0][1] - exp_trans) < 1e-9
    assert abs(transversion[0][1] - exp_transv) < 1e-9
    assert transition[0][1] > transversion[0][1]


def test_dna_distance_excludes_gap_sites():
    # '-' sites are not comparable -> 0 differences among 3 comparable sites
    dm = _dna_distance_matrix(_aln("ATGC", "AT-C"), "jc69")

    assert dm[0][1] == 0.0


# ── Worker ────────────────────────────────────────────────────────────────


def test_worker_jc69_builds_tree(tmp_path):
    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(">a\nATGC\n>b\nATGC\n>c\nATTC\n", encoding="utf-8")

    worker = _DistanceTreeWorker(str(aln_file), "jc69", "nj", 0)
    results, errors = [], []
    worker.finished_ok.connect(results.append)
    worker.finished_err.connect(errors.append)

    worker.run()

    assert not errors, errors
    assert results[0]["n_taxa"] == 3
    assert results[0]["newick"].startswith("(")


def test_worker_warns_when_bootstrap_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.distance_tree_tab._HAS_BOOTSTRAP", False)

    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(">a\nATGC\n>b\nATGC\n>c\nATTC\n", encoding="utf-8")

    worker = _DistanceTreeWorker(str(aln_file), "jc69", "nj", 100)
    results = []
    worker.finished_ok.connect(results.append)

    worker.run()

    assert results[0]["n_bootstrap"] == 0
    assert "Bootstrap support is unavailable" in results[0]["warning"]


def test_on_result_logs_warning(qapp, tmp_path):
    tab = DistanceTreeTab()
    tab._out_edit.setText(str(tmp_path / "t.nwk"))

    tab._on_result(
        {
            "matrix": [[0.0]],
            "names": ["a"],
            "newick": "(a);",
            "n_taxa": 1,
            "n_bootstrap": 0,
            "warning": "bootstrap skipped",
        }
    )

    assert "bootstrap skipped" in tab.log_area.toPlainText()


def test_clear_resets_bootstrap_to_default(qapp):
    tab = DistanceTreeTab()
    tab._bootstrap_spin.setValue(500)

    tab._clear_all()

    assert tab._bootstrap_spin.value() == 1000


# ── View Tree button ──────────────────────────────────────────────────────


def test_view_tree_button_hidden_initially(qapp):
    tab = DistanceTreeTab()
    texts = [btn.text() for btn in tab.findChildren(QPushButton)]

    assert "View Tree" in texts
    assert tab._view_tree_btn.isHidden()


def test_example_button_moved_to_input_group_left_of_browse(qapp):
    tab = DistanceTreeTab()

    # Example is no longer in the status bar
    assert tab.status_layout.indexOf(tab._example_btn) == -1

    # Example shares the file row with Browse, positioned to its left
    group_layout = tab._browse_btn.parent().layout()  # "Input and Method" group
    file_row = group_layout.itemAt(0).layout()
    assert file_row.indexOf(tab._example_btn) >= 0
    assert file_row.indexOf(tab._browse_btn) >= 0
    assert file_row.indexOf(tab._example_btn) < file_row.indexOf(tab._browse_btn)


def test_view_tree_button_visible_after_successful_result(qapp, tmp_path):
    tab = DistanceTreeTab()
    out = tmp_path / "tree.nwk"
    tab._out_edit.setText(str(out))

    tab._on_result(
        {
            "matrix": [[0.0]],
            "names": ["a"],
            "newick": "(a);",
            "n_taxa": 1,
            "n_bootstrap": 0,
        }
    )

    assert not tab._view_tree_btn.isHidden()
    assert tab._last_treefile == str(out)
    assert out.exists()


def test_clear_hides_view_tree_button(qapp, tmp_path):
    tab = DistanceTreeTab()
    out = tmp_path / "tree.nwk"
    tab._out_edit.setText(str(out))
    tab._on_result(
        {"matrix": [[0.0]], "names": ["a"], "newick": "(a);", "n_taxa": 1, "n_bootstrap": 0}
    )
    assert not tab._view_tree_btn.isHidden()

    tab._clear_all()

    assert tab._view_tree_btn.isHidden()
    assert tab._last_treefile == ""


def test_open_tree_viewer_switches_to_toytree_tab(qapp, tmp_path):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = DistanceTreeTab()
    tab._open_tree_viewer()  # no tree yet -> no-op

    out = tmp_path / "tree.nwk"
    out.write_text("(a,b);", encoding="utf-8")
    tab._last_treefile = str(out)

    opened = []
    toytree_tab = ToytreeVisualizationTab()
    tabs = SimpleNamespace(
        count=lambda: 1,
        widget=lambda i: toytree_tab,
        setCurrentIndex=lambda i: opened.append(i),
    )
    window = SimpleNamespace(
        open_toytree_visualization_tab=lambda: None, tabs=tabs
    )
    tab.window = lambda: window

    tab._open_tree_viewer()

    assert toytree_tab._file_edit.text() == str(out)
    assert opened == [0]


# ── Matrix diagonal semantics ─────────────────────────────────────────────


def test_populate_table_shows_zero_diagonal(qapp):
    tab = DistanceTreeTab()
    matrix = [[0.0, 0.2], [0.2, 0.0]]

    tab._populate_table(matrix, ["a", "b"])

    assert tab._table.item(0, 0).text() == "0.0000"
    assert tab._table.item(1, 1).text() == "0.0000"
    assert tab._table.item(0, 1).text() == "0.2000"


def test_export_csv_writes_zero_diagonal(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    tab = DistanceTreeTab()
    tab._names = ["a", "b"]
    tab._matrix_data = [[0.0, 0.2], [0.2, 0.0]]
    out = tmp_path / "matrix.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), ""))
    )

    tab._export_csv()

    content = out.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    assert lines[1] == "a,0.000000,0.200000"
    assert lines[2] == "b,0.200000,0.000000"
