"""Regression tests for the Sequence Concatenation tab.

The concat tab is the only tab using the shared ``BaseWorker`` +
``start_worker`` threading pattern. A worker-finish race used to destroy the
still-running ``QThread`` (Qt fatal: "QThread: Destroyed while thread is
still running"), which aborted the entire application when the run completed.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox, QPushButton

from modules.partition_concat_tab import (
    PartitionConcatTab,
    _ConcatPartitionWorker,
    _concatenate_alignments,
    _sanitize_gene_names,
)
from utils.common_components import BaseTabWidget, BaseWorker


class _SlowFinishWorker(BaseWorker):
    """Emit ``finished``, then keep the worker thread alive briefly so the
    main thread handles the finished signal while the QThread is still
    running — the exact condition that triggered the crash.
    """

    def run(self):
        self.emit_finished("done")
        time.sleep(0.15)


def test_worker_finish_releases_thread_without_destroying_running_qthread(qapp):
    host = BaseTabWidget("Host", "file")
    # Keep a strong reference to the worker (as PartitionConcatTab does via
    # self._worker); an inline worker can otherwise be garbage-collected.
    worker = _SlowFinishWorker()
    host.start_worker(worker)

    # Drive the event loop until the worker finishes and the thread reference
    # is released. With the old code this aborts the process (Qt fatal).
    deadline = time.time() + 5
    while host.worker_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()

    assert host.worker_thread is None


# ── Gene-name sanitization ────────────────────────────────────────────────


def test_sanitize_gene_names_cleans_invalid_chars_and_duplicates():
    names, changes = _sanitize_gene_names(["gene 1", "16S rRNA", "gene 1", "COI"])

    assert names == ["gene_1", "16S_rRNA", "gene_1_2", "COI"]
    assert len(changes) == 3
    assert '"gene 1" → "gene_1"' in changes
    assert '"gene 1" → "gene_1_2"' in changes


def test_sanitize_gene_names_handles_empty_and_symbol_only_names():
    names, changes = _sanitize_gene_names(["-", ""])

    assert names == ["gene1", "gene2"]
    assert len(changes) == 2


# ── Validate Input button ─────────────────────────────────────────────────


def test_validate_button_replaces_clear_all(qapp):
    tab = PartitionConcatTab()
    texts = [btn.text() for btn in tab.findChildren(QPushButton)]

    assert "Validate Input" in texts
    assert "Clear All" not in texts


def test_partition_format_combo_has_iqtree_and_mrbayes(qapp):
    tab = PartitionConcatTab()
    assert tab._format_combo.count() == 2
    assert tab._format_combo.itemData(0) == "iqtree"
    assert tab._format_combo.itemData(1) == "mrbayes"


def test_result_folder_button_opens_output_dir(qapp, monkeypatch, tmp_path):
    tab = PartitionConcatTab()
    opened = []
    monkeypatch.setattr(
        "modules.partition_concat_tab.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )
    assert tab.open_output_btn.text() == "Result Folder"

    tab._open_output_folder()
    assert tab.status_label.text() == "No output folder selected yet."

    out_dir = tmp_path / "out"
    tab._output_dir_edit.setText(str(out_dir))
    tab._open_output_folder()
    assert tab.status_label.text() == "Output folder does not exist yet."

    out_dir.mkdir()
    tab._open_output_folder()
    assert opened == [QUrl.fromLocalFile(str(out_dir)).toString()]


def test_validate_input_warns_without_files(qapp, monkeypatch):
    tab = PartitionConcatTab()
    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: warned.append(args[2])
    )

    tab._validate_input()

    assert len(warned) == 1
    assert "must be fixed" in warned[0]


def test_run_writes_sanitized_nexus_charset(qapp, monkeypatch, tmp_path):
    gene1 = tmp_path / "gene 1.fasta"
    gene2 = tmp_path / "gene2.fasta"
    gene1.write_text(">taxonA\nATGC\n>taxonB\nATGC\n", encoding="utf-8")
    gene2.write_text(">taxonA\nACGTACGT\n>taxonB\nACGTACGT\n", encoding="utf-8")

    tab = PartitionConcatTab()
    tab._output_dir_edit.setText(str(tmp_path))
    for f in (gene1, gene2):
        item = QListWidgetItem(f.name)
        item.setData(256, str(f))
        tab._file_list.addItem(item)

    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    # Run the worker synchronously instead of via a real QThread.
    monkeypatch.setattr(tab, "start_worker", lambda worker: worker.run())

    tab.run()

    nex = (tmp_path / "concat_partition.nex").read_text(encoding="utf-8")
    assert "charset gene_1 = 1-4;" in nex
    assert "charset gene2 = 5-12;" in nex


def test_run_writes_mrbayes_nexus_data_fills_missing_taxa_with_question_mark(
    qapp, monkeypatch, tmp_path
):
    gene1 = tmp_path / "gene1.fasta"
    gene2 = tmp_path / "gene2.fasta"
    gene1.write_text(">taxonA\nATGC\n>taxonB\nATGC\n", encoding="utf-8")
    gene2.write_text(
        ">taxonA\nACGTACGT\n>taxonB\nACGTACGT\n>taxonC\nACGTACGT\n",
        encoding="utf-8",
    )

    tab = PartitionConcatTab()
    tab._output_dir_edit.setText(str(tmp_path))
    for f in (gene1, gene2):
        item = QListWidgetItem(f.name)
        item.setData(256, str(f))
        tab._file_list.addItem(item)
    tab._format_combo.setCurrentIndex(tab._format_combo.findData("mrbayes"))

    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    # Run the worker synchronously instead of via a real QThread.
    monkeypatch.setattr(tab, "start_worker", lambda worker: worker.run())

    tab.run()

    nex = (tmp_path / "concat_partition.nex").read_text(encoding="utf-8")
    assert "BEGIN DATA;" in nex
    assert "DATATYPE=DNA" in nex
    assert "NTAX=3 NCHAR=12" in nex
    # taxonC is absent from gene1 -> its 4 leading positions are '?' (MrBayes)
    assert "taxonC ????ACGTACGT" in nex
    assert "taxonA ATGCACGTACGT" in nex
    assert "charset gene1 = 1-4;" in nex
    assert "charset gene2 = 5-12;" in nex
    # the IQ-TREE default keeps '-' for the same input
    ids, seqs, _, _ = _concatenate_alignments(
        [str(gene1), str(gene2)], ["gene1", "gene2"], missing_char="-"
    )
    assert seqs[ids.index("taxonC")] == "----ACGTACGT"


# ── Format-aware completion summary ───────────────────────────────────────


def _worker_summary(tmp_path, fmt: str) -> str:
    gene1 = tmp_path / "g1.fasta"
    gene1.write_text(">a\nATGC\n>b\nATGC\n", encoding="utf-8")
    worker = _ConcatPartitionWorker(
        [str(gene1)],
        ["gene1"],
        str(tmp_path / "concat.fasta"),
        str(tmp_path / "concat.nex"),
        "DNA",
        fmt,
    )
    messages = []
    worker.finished.connect(messages.append)
    worker.run()
    return messages[0]


def test_worker_summary_iqtree_format_mentions_iqtree(tmp_path):
    summary = _worker_summary(tmp_path, "iqtree")

    assert "Ready for IQ-TREE" in summary
    assert "NEXUS DATA (MrBayes)" in summary
    assert "Ready for IQ-TREE, MrBayes, or RAxML-NG" not in summary


def test_worker_summary_mrbayes_format_mentions_mrbayes(tmp_path):
    summary = _worker_summary(tmp_path, "mrbayes")

    assert "Ready for MrBayes" in summary
    assert "Ready for IQ-TREE, MrBayes, or RAxML-NG" not in summary
