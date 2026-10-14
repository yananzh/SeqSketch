"""Tests for the Distance Tree Construction tab."""

import math
import os
from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize("model", ["jc69", "k80"])
def test_missing_comparable_sites_are_not_zero_distance(model):
    with pytest.raises(ValueError, match="t1 and t0"):
        _dna_distance_matrix(_aln("AAAA----", "----TTTT", "AAAATTTT"), model)


@pytest.mark.parametrize("model", ["jc69", "k80"])
def test_rna_uracil_matches_thymine(model):
    assert _dna_distance_matrix(_aln("ACGU", "ACGT"), model)[0][1] == 0


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


def test_worker_bootstrap_support_values_are_valid_percentages(tmp_path):
    # BioPython's NJ names internal nodes Inner1..Inner(n-2); at 13 taxa the
    # two-digit names made the old ")Inner11 98.00:" regex post-processing emit
    # labels like "198.00" (the node-number digit glued onto the support value).
    # Every internal label must be a plain support percentage in [0, 100].
    import re

    import numpy as np

    np.random.seed(20261014)
    swap = {"A": "C", "C": "G", "G": "T", "T": "A"}
    records = []
    for i in range(13):
        chars = list("ACGT" * 15)
        # 5 group-specific columns make four well-separated clusters...
        group = i // 4
        for j in range(group * 5, group * 5 + 5):
            chars[j] = swap[chars[j]]
        # ...and one unique column per taxon separates members inside a group.
        chars[40 + i] = swap[chars[40 + i]]
        records.append(f">t{i:02d}\n{''.join(chars)}\n")
    aln_file = tmp_path / "aln13.fasta"
    aln_file.write_text("".join(records), encoding="utf-8")

    worker = _DistanceTreeWorker(str(aln_file), "jc69", "nj", 50)
    results, errors = [], []
    worker.finished_ok.connect(results.append)
    worker.finished_err.connect(errors.append)

    worker.run()

    assert not errors, errors
    newick = results[0]["newick"]
    assert "Inner" not in newick
    labels = re.findall(r"\)([0-9.]+)(?=[;:])", newick)
    assert labels, "expected bootstrap support labels on internal nodes"
    for label in labels:
        assert 0.0 <= float(label) <= 100.0, f"support value out of range: {label}"


def test_worker_without_bootstrap_has_no_placeholder_node_names(tmp_path):
    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(">a\nATGC\n>b\nATGC\n>c\nATTC\n", encoding="utf-8")

    worker = _DistanceTreeWorker(str(aln_file), "jc69", "nj", 0)
    results = []
    worker.finished_ok.connect(results.append)

    worker.run()

    assert "Inner" not in results[0]["newick"]


def test_worker_stop_cancels_before_any_work(tmp_path):
    """A worker stopped before running must report cancellation, not compute."""
    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(">a\nATGC\n>b\nATGC\n>c\nATTC\n", encoding="utf-8")

    worker = _DistanceTreeWorker(str(aln_file), "jc69", "nj", 1000)
    errors, oks = [], []
    worker.finished_err.connect(errors.append)
    worker.finished_ok.connect(oks.append)
    worker.stop()

    worker.run()

    assert errors == ["Stopped by user"]
    assert not oks


def test_worker_stop_halts_bootstrap_after_first_replicate(tmp_path):
    """The 1000-replicate bootstrap loop must check the stop flag between
    replicates — it used to be un-cancellable (and kept burning CPU after the
    tab closed, since request_task_stop had nothing to reach)."""
    records = "".join(
        f">t{i}\n{'ACGT' * 15}\n".replace("ACGT", "ACGT", 1) for i in range(4)
    )
    aln_file = tmp_path / "aln.fasta"
    aln_file.write_text(records, encoding="utf-8")

    worker = _DistanceTreeWorker(str(aln_file), "jc69", "nj", 1000)
    errors, oks, progress = [], [], []
    worker.finished_err.connect(errors.append)
    worker.finished_ok.connect(oks.append)

    def on_progress(current, total):
        progress.append(current)
        worker.stop()  # cancel as soon as the first replicate completes

    worker.progress.connect(on_progress)

    worker.run()

    assert errors == ["Stopped by user"]
    assert not oks
    assert len(progress) <= 2, "cancellation must preempt the remaining replicates"


def test_stop_button_wiring_and_cancelled_status(qapp, tmp_path):
    tab = DistanceTreeTab()
    assert tab._stop_btn.isHidden()

    tab._set_running(True)
    assert not tab._stop_btn.isHidden()
    assert not tab._run_btn.isEnabled()

    tab._on_error("Stopped by user")
    assert tab._stop_btn.isHidden()
    assert tab._run_btn.isEnabled()
    assert tab.status_label.text() == "Stopped by user"
    assert tab._thread is None


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


def test_example_button_immediately_after_run(qapp):
    tab = DistanceTreeTab()

    # Order: [Run] [Stop] [Example] …
    assert tab.status_layout.indexOf(tab._stop_btn) == (
        tab.status_layout.indexOf(tab._run_btn) + 1
    )
    assert tab.status_layout.indexOf(tab._example_btn) == (
        tab.status_layout.indexOf(tab._run_btn) + 2
    )



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
