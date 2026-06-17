"""
Sequence Concatenation & Partition File Generator
One-step workflow:
  Provide aligned gene/locus FASTA files → produces a concatenated supermatrix
  FASTA file + a NEXUS-format partition file compatible with IQ-TREE,
  MrBayes, and RAxML-NG.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, BaseWorker


def _wrap_layout(layout) -> QWidget:
    container = QWidget()
    container.setLayout(layout)
    return container


# ---------------------------------------------------------------------------
# Drag-and-drop QListWidget with placeholder when empty
# ---------------------------------------------------------------------------
class _DropFileList(QListWidget):
    def __init__(self, placeholder: str = "Drop FASTA files here…", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._placeholder = placeholder
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:
        if e:
            mime = e.mimeData()
            if mime and mime.hasUrls():
                e.acceptProposedAction()
                return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:
        if e:
            e.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event:
            mime = event.mimeData()
            if mime:
                for url in mime.urls():
                    path = url.toLocalFile()
                    if path and os.path.isfile(path):
                        existing = [
                            it.data(256)
                            for i in range(self.count())
                            if (it := self.item(i)) is not None
                        ]
                        if path not in existing:
                            item = QListWidgetItem(os.path.basename(path))
                            item.setData(256, path)
                            self.addItem(item)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if self.count() == 0:
            vp = self.viewport()
            if vp is None:
                return
            painter = QPainter(vp)
            painter.save()
            col = self.palette().placeholderText().color()
            painter.setPen(col)
            painter.drawText(
                vp.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._placeholder,
            )
            painter.restore()


# ---------------------------------------------------------------------------
# FASTA I/O helpers
# ---------------------------------------------------------------------------
def _read_fasta(filepath: str) -> tuple[list[str], list[str]]:
    ids, seqs = [], []
    current_id, current_seq = "", ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()
                if line.startswith(">"):
                    if current_id:
                        ids.append(current_id)
                        seqs.append(current_seq)
                    current_id = line[1:]
                    current_seq = ""
                else:
                    current_seq += line
            if current_id:
                ids.append(current_id)
                seqs.append(current_seq)
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="latin-1") as f:
            for line in f:
                line = line.rstrip()
                if line.startswith(">"):
                    if current_id:
                        ids.append(current_id)
                        seqs.append(current_seq)
                    current_id = line[1:]
                    current_seq = ""
                else:
                    current_seq += line
            if current_id:
                ids.append(current_id)
                seqs.append(current_seq)
    except Exception as e:
        raise RuntimeError(f"Error reading {filepath}: {e}")
    return ids, seqs


def _write_fasta(filepath: str, ids: list[str], seqs: list[str]) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        for id_, seq in zip(ids, seqs):
            f.write(f">{id_}\n{seq}\n")


def _concatenate_alignments(
    files: list[str], gene_names: list[str] | None = None
) -> tuple[list[str], list[str], list[tuple[str, int, int]]]:
    if not files:
        raise ValueError("No files provided")

    all_taxa: list[str] | None = None
    concat_seqs: dict[str, str] = {}
    partitions: list[tuple[str, int, int]] = []
    pos = 1

    for i, fpath in enumerate(files):
        if not os.path.isfile(fpath):
            raise RuntimeError(f"File not found: {fpath}")
        gene_name = (
            gene_names[i] if gene_names and i < len(gene_names) else f"gene{i + 1}"
        )
        ids, seqs = _read_fasta(fpath)
        if not ids:
            raise ValueError(f"No sequences in {fpath}")
        lengths = {len(s) for s in seqs}
        if len(lengths) > 1:
            raise ValueError(
                f"Unaligned sequences in {fpath} (lengths: {sorted(lengths)})"
            )
        seq_len = len(seqs[0]) if seqs else 0
        if all_taxa is None:
            all_taxa = ids
            for tid in ids:
                concat_seqs[tid] = ""
        else:
            if set(ids) != set(all_taxa):
                missing_in_file = set(all_taxa) - set(ids)
                missing_in_master = set(ids) - set(all_taxa)
                detail = ""
                if missing_in_file:
                    detail += f" missing in {gene_name}: {sorted(missing_in_file)[:5]}"
                if missing_in_master:
                    detail += f" extra in {gene_name}: {sorted(missing_in_master)[:5]}"
                raise ValueError(f"Taxa mismatch in {fpath}{detail}")
        for tid, seq in zip(ids, seqs):
            concat_seqs[tid] += seq
        partitions.append((gene_name, pos, pos + seq_len - 1))
        pos += seq_len

    final_ids = all_taxa or []
    final_seqs = [concat_seqs[tid] for tid in final_ids]
    return final_ids, final_seqs, partitions


# ---------------------------------------------------------------------------
# NEXUS partition file writer
# ---------------------------------------------------------------------------
def _write_nexus_partition(
    filepath: str,
    partitions: list[tuple[str, int, int]],
    seq_type: str = "DNA",
) -> None:
    """Write a NEXUS partition file in IQ-TREE-compatible charset format.

    Output format::

        #NEXUS
        BEGIN SETS;
          charset gene1 = 1-279;
          charset gene2 = 280-824;
        END;
    """
    charset_lines = []
    for gene, start, end in partitions:
        charset_lines.append(f"    charset {gene} = {start}-{end};")

    total_len = partitions[-1][2] if partitions else 0

    content = f"""#NEXUS
[Generated by SeqSketch - Sequence Concatenation & Partition]
[Sequence type: {seq_type}]
[Gene count: {len(partitions)}]
[Total length: {total_len} positions]

BEGIN SETS;
{chr(10).join(charset_lines)}
END;
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# One-step concatenation + partition worker
# ---------------------------------------------------------------------------
class _ConcatPartitionWorker(BaseWorker):
    progress = pyqtSignal(str)

    def __init__(
        self,
        files: list[str],
        gene_names: list[str],
        concat_output: str,
        partition_output: str,
        seq_type: str = "DNA",
    ):
        super().__init__()
        self.files = files
        self.gene_names = gene_names
        self.concat_output = concat_output
        self.partition_output = partition_output
        self.seq_type = seq_type

    def run(self):
        try:
            # --- Stage 1: Concatenate ---
            self.progress.emit("⏳ Concatenating aligned gene sequences…")
            ids, seqs, partitions = _concatenate_alignments(self.files, self.gene_names)
            total_len = len(seqs[0]) if seqs else 0

            _write_fasta(self.concat_output, ids, seqs)
            self.progress.emit(
                f"✔ Concatenation: {len(ids)} taxa, "
                f"{len(partitions)} genes, {total_len} positions"
            )

            # --- Stage 2: Write NEXUS partition file ---
            self.progress.emit("⏳ Writing NEXUS partition file…")
            _write_nexus_partition(self.partition_output, partitions, self.seq_type)
            self.progress.emit(f"✔ Partition file written: {self.partition_output}")

            # --- Build summary ---
            summary = (
                f"✔ Concatenation + Partition complete\n"
                f"  Taxa:         {len(ids)}\n"
                f"  Genes:        {len(partitions)}\n"
                f"  Total length: {total_len} bp/aa\n"
                f"  Concat FASTA: {self.concat_output}\n"
                f"  Partition:    {self.partition_output}\n"
            )
            for gene, start, end in partitions:
                summary += f"    {gene}: {start}-{end} ({end - start + 1} bp)\n"

            summary += (
                "\nReady for IQ-TREE, MrBayes, or RAxML-NG with partition-aware models."
            )
            self.emit_finished(summary)

        except Exception as exc:
            self.emit_error(str(exc))


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------
class PartitionConcatTab(BaseTabWidget):
    def __init__(self, status_callback=None, parent=None):
        self._status_callback = status_callback
        self._worker: _ConcatPartitionWorker | None = None
        super().__init__("Sequence Concatenation", "file")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # ---- Input section ----
        input_group = QGroupBox(self.tr("Input – Aligned Gene Files"))
        input_layout = QVBoxLayout(input_group)

        self._file_list = _DropFileList(
            self.tr("Drag & drop aligned FASTA files here, or click Choose")
        )
        self._file_list.setMinimumHeight(100)
        self._file_list.setMaximumHeight(160)
        input_layout.addWidget(self._file_list)

        file_btn_row = QHBoxLayout()
        choose_btn = QPushButton(self.tr("Choose"))
        choose_btn.clicked.connect(self._add_files)
        remove_btn = QPushButton(self.tr("Remove Selected"))
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton(self.tr("Clear All"))
        clear_btn.clicked.connect(self._clear_files)
        file_btn_row.addWidget(choose_btn)
        file_btn_row.addWidget(remove_btn)
        file_btn_row.addWidget(clear_btn)
        file_btn_row.addStretch()
        input_layout.addLayout(file_btn_row)

        self.add_content_widget(input_group)

        # ---- Parameters section ----
        param_group = QGroupBox(self.tr("Parameters"))
        param_form = QFormLayout(param_group)
        param_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        param_form.setVerticalSpacing(10)
        param_form.setHorizontalSpacing(12)

        # Sequence type
        self._seqtype_combo = QComboBox()
        self._seqtype_combo.addItems(["DNA", "Protein"])
        self._seqtype_combo.setFixedWidth(140)
        self._seqtype_combo.setToolTip(self.tr("DNA: nucleotide; Protein: amino-acid"))
        seqtype_row = QHBoxLayout()
        seqtype_row.setContentsMargins(0, 0, 0, 0)
        seqtype_row.addWidget(self._seqtype_combo)
        seqtype_row.addStretch()
        param_form.addRow(self.tr("Sequence type:"), _wrap_layout(seqtype_row))

        # Partition output format
        self._format_combo = QComboBox()
        self._format_combo.addItems(["NEXUS (MrBayes / IQ-TREE)", "RAxML-style"])
        self._format_combo.setFixedWidth(240)
        self._format_combo.setToolTip(
            self.tr(
                "NEXUS: charset + SETS block for MrBayes & IQ-TREE.\n"
                "RAxML-style: plain text model, gene = start-end lines."
            )
        )
        format_row = QHBoxLayout()
        format_row.setContentsMargins(0, 0, 0, 0)
        format_row.addWidget(self._format_combo)
        format_row.addStretch()
        param_form.addRow(self.tr("Partition format:"), _wrap_layout(format_row))

        # Output directory
        outdir_row = QHBoxLayout()
        outdir_row.setContentsMargins(0, 0, 0, 0)
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText(
            self.tr("Directory for concatenated FASTA and partition file")
        )
        outdir_browse = QPushButton(self.tr("Browse"))
        outdir_browse.setFixedWidth(80)
        outdir_browse.clicked.connect(self._browse_output_dir)
        outdir_row.addWidget(self._output_dir_edit, 1)
        outdir_row.addWidget(outdir_browse)
        param_form.addRow(self.tr("Output directory:"), _wrap_layout(outdir_row))

        # Output file prefix
        self._prefix_edit = QLineEdit("concat_partition")
        self._prefix_edit.setFixedWidth(240)
        self._prefix_edit.setToolTip(
            self.tr("Output files: <prefix>.fasta and <prefix>.nex")
        )
        prefix_row = QHBoxLayout()
        prefix_row.setContentsMargins(0, 0, 0, 0)
        prefix_row.addWidget(self._prefix_edit)
        prefix_row.addStretch()
        param_form.addRow(self.tr("Output prefix:"), _wrap_layout(prefix_row))

        self.add_content_widget(param_group)

        # ---- Primary actions (bottom) ----
        action_row = QHBoxLayout()
        self.run_btn = QPushButton(self.tr("▶  Run Concatenation"))
        self.run_btn.setMinimumHeight(36)
        self.run_btn.clicked.connect(self.run)
        self.clear_btn = QPushButton(self.tr("Clear All"))
        self.clear_btn.clicked.connect(self.clear)
        action_row.addWidget(self.run_btn)
        action_row.addWidget(self.clear_btn)
        # Replace status area with action buttons at bottom
        self.main_layout.removeItem(self.status_layout)
        for i in range(self.status_layout.count()):
            w = self.status_layout.itemAt(i).widget()
            if w and w is not self.help_btn:
                w.hide()
        action_row.addStretch()
        action_row.addWidget(self.help_btn)
        self.main_layout.addLayout(action_row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr("Select alignment files"),
            "",
            self.tr("FASTA files (*.fasta *.fa *.fas *.txt);;All Files (*)"),
        )
        for path in paths:
            existing = [
                it.data(256)
                for i in range(self._file_list.count())
                if (it := self._file_list.item(i)) is not None
            ]
            if path not in existing:
                item = QListWidgetItem(os.path.basename(path))
                item.setData(256, path)
                self._file_list.addItem(item)
        if paths:
            self.show_status(self.tr("Added {n} file(s)").format(n=len(paths)))

    def _remove_selected(self) -> None:
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    def _clear_files(self) -> None:
        self._file_list.clear()
        self.show_status(self.tr("File list cleared"))

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select output directory"),
            self._output_dir_edit.text().strip(),
        )
        if directory:
            self._output_dir_edit.setText(directory)

    # ------------------------------------------------------------------
    # Core actions
    # ------------------------------------------------------------------
    def run(self) -> None:
        """One-step: concatenate + generate NEXUS partition file."""
        # Collect files and gene names
        files: list[str] = []
        gene_names: list[str] = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item:
                fpath = item.data(256)
                if fpath:
                    fname = os.path.splitext(os.path.basename(fpath))[0]
                    files.append(fpath)
                    gene_names.append(fname)

        if not files:
            self.show_status(self.tr("Please add at least one aligned FASTA file"))
            self.log_message(self.tr("No input files selected."), "WARNING")
            return

        # Validate output directory
        out_dir = self._output_dir_edit.text().strip()
        if not out_dir:
            self.show_status(self.tr("Please select an output directory"))
            self.log_message(self.tr("Output directory is required."), "WARNING")
            return
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as exc:
                self.show_status(self.tr("Cannot create output directory"))
                self.log_message(str(exc), "ERROR")
                return

        prefix = self._prefix_edit.text().strip() or "concat_partition"
        concat_path = os.path.join(out_dir, f"{prefix}.fasta")
        partition_ext = "nex"
        if "RAxML" in self._format_combo.currentText():
            partition_ext = "txt"
        partition_path = os.path.join(out_dir, f"{prefix}.{partition_ext}")

        seq_type = "DNA" if self._seqtype_combo.currentText() == "DNA" else "AA"

        self.run_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.log_message(self.tr("Starting concatenation workflow…"))
        self.log_message(self.tr("  Input files: {n}").format(n=len(files)))

        self._worker = _ConcatPartitionWorker(
            files=files,
            gene_names=gene_names,
            concat_output=concat_path,
            partition_output=partition_path,
            seq_type=seq_type,
        )
        self._worker.progress.connect(self.show_status)
        self.start_worker(self._worker)

    def clear(self) -> None:
        """Reset all inputs."""
        self._file_list.clear()
        self._output_dir_edit.clear()
        self._prefix_edit.setText("concat_partition")
        self._seqtype_combo.setCurrentIndex(0)
        self.show_status(self.tr("Cleared"))

    # ------------------------------------------------------------------
    # Worker result handlers
    # ------------------------------------------------------------------
    def handle_worker_finished(self, message: str) -> None:
        super().handle_worker_finished(message)
        self.run_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.log_message(message)
        if self._status_callback:
            self._status_callback("Concatenation + partition complete", 0)

    def handle_worker_error(self, error_msg: str) -> None:
        super().handle_worker_error(error_msg)
        self.run_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        if self._status_callback:
            self._status_callback(f"Error: {error_msg}", 0)

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------
    def show_help(self) -> None:
        from PyQt6.QtWidgets import QDialog, QTextBrowser

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Concatenation & Partition Help"))
        dlg.resize(640, 520)
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._help_html())
        lay.addWidget(browser)
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    def _help_html(self) -> str:
        return self.tr("""
<h2>Sequence Concatenation &amp; Partition</h2>
<p>One-step workflow: drop in aligned gene FASTA files and produce both a
concatenated supermatrix and a NEXUS-format partition file in one click.</p>

<h3>Input</h3>
<ul>
  <li>Add multiple <b>aligned</b> gene/locus FASTA files via drag &amp; drop
  or the <b>Choose</b> button.</li>
  <li>Each file represents one gene partition. Gene names are derived from
  the file name (without extension).</li>
  <li>All files must share the same set of taxa — missing or extra taxa
  will be flagged as an error.</li>
  <li>Sequences within each file must be of equal length (properly aligned).</li>
</ul>

<h3>Parameters</h3>
<ul>
  <li><b>Sequence type</b> – DNA (nucleotide) or Protein (amino acid).
  Affects the NEXUS header.</li>
  <li><b>Partition format</b> – NEXUS (MrBayes / IQ-TREE) generates a
  <code>#NEXUS</code> block with <code>BEGIN SETS;</code> charset
  definitions. RAxML-style writes plain text <code>model, gene =
  start-end</code> lines.</li>
  <li><b>Output directory</b> – where the concatenated FASTA and partition
  file are written.</li>
  <li><b>Output prefix</b> – files will be named
  <code>&lt;prefix&gt;.fasta</code> and <code>&lt;prefix&gt;.nex</code>
  (or <code>.txt</code> for RAxML).</li>
</ul>

<h3>Output Files</h3>
<ul>
  <li><b>Concatenated FASTA</b> – single supermatrix file with all genes
  joined end-to-end for each taxon.</li>
  <li><b>Partition file</b> – NEXUS format defining gene boundaries.
  Ready for IQ-TREE, MrBayes, or RAxML-NG.</li>
</ul>

<h3>Next Steps</h3>
<p>Use the concatenated FASTA and partition file with the
<b>Tree Construction (IQ-TREE)</b> tab to infer a partition-aware
phylogeny, or load them directly into MrBayes / RAxML-NG.</p>

<h3>Tips</h3>
<ul>
  <li>Common gene names: COI, 16S, 18S, 28S, ITS, rbcL, matK.</li>
  <li>Ensure all input files are properly aligned before concatenation.</li>
  <li>The generated NEXUS partition file can be manually edited if needed.</li>
  <li>Taxa names must match exactly across all input files.</li>
</ul>
""")
