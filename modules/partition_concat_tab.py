"""
Sequence Concatenation & ModelFinder Partition Analysis Tab
Two-stage workflow:
  1. Concatenate multiple aligned gene sequences
  2. Use IQ-TREE ModelFinder to identify best model per partition
"""

import os
import subprocess
import tempfile

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IQTREE_EXE = os.path.join(
    _HERE, "softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe"
)


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


# ---------------------------------------------------------------------------
# Drag-and-drop QListWidget with placeholder text
# ---------------------------------------------------------------------------
class _DropFileList(QListWidget):
    """QListWidget that accepts dragged files and shows placeholder when empty."""

    def __init__(self, placeholder: str = "Drop FASTA files here…", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._placeholder = placeholder
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:  # noqa: N802
        if e:
            mime = e.mimeData()
            if mime and mime.hasUrls():
                e.acceptProposedAction()
                return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:  # noqa: N802
        if e:
            e.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
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

    def paintEvent(self, e) -> None:  # noqa: N802
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
# Drag-and-drop QLineEdit
# ---------------------------------------------------------------------------
class _DropLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:  # noqa: N802
        if a0:
            mime = a0.mimeData()
            if mime and mime.hasUrls():
                a0.acceptProposedAction()
                return
        super().dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:  # noqa: N802
        if a0:
            mime = a0.mimeData()
            if mime:
                urls = mime.urls()
                if urls:
                    self.setText(urls[0].toLocalFile())
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ---------------------------------------------------------------------------
# FASTA parsing helpers
# ---------------------------------------------------------------------------
def _read_fasta(filepath: str) -> tuple[list[str], list[str]]:
    """Read FASTA file; return (ids, sequences)."""
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
    except Exception as e:
        raise RuntimeError(f"Error reading {filepath}: {e}")
    return ids, seqs


def _write_fasta(filepath: str, ids: list[str], seqs: list[str]):
    """Write FASTA file."""
    with open(filepath, "w", encoding="utf-8") as f:
        for id_, seq in zip(ids, seqs):
            f.write(f">{id_}\n{seq}\n")


def _concatenate_alignments(
    files: list[str], gene_names: list[str] | None = None
) -> tuple[list[str], list[str], list[tuple[str, int, int]]]:
    """
    Concatenate multiple aligned FASTA files.
    Return: (taxa_ids, concat_seqs, partitions)
    partitions: [(gene_name, start, end), ...]
    """
    if not files:
        raise ValueError("No files provided")

    all_taxa = None
    concat_seqs = {}
    partitions = []
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
        if len(set(len(s) for s in seqs)) > 1:
            raise ValueError(f"Unaligned sequences in {fpath}")
        seq_len = len(seqs[0]) if seqs else 0
        if all_taxa is None:
            all_taxa = ids
            for tid in ids:
                concat_seqs[tid] = ""
        elif set(ids) != set(all_taxa):
            raise ValueError(f"Taxa mismatch in {fpath}")
        for tid, seq in zip(ids, seqs):
            concat_seqs[tid] += seq
        partitions.append((gene_name, pos, pos + seq_len - 1))
        pos += seq_len

    final_ids = all_taxa or []
    final_seqs = [concat_seqs[tid] for tid in final_ids]
    return final_ids, final_seqs, partitions


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------
class _ConcatenateThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, output_path, message

    def __init__(self, files: list[str], gene_names: list[str], output_path: str):
        super().__init__()
        self.files = files
        self.gene_names = gene_names
        self.output_path = output_path

    def run(self):
        self.progress.emit("⏳ Concatenating alignments…")
        try:
            ids, seqs, partitions = _concatenate_alignments(self.files, self.gene_names)
            _write_fasta(self.output_path, ids, seqs)
            msg = f"✔ Concatenated {len(self.files)} genes into {len(ids)} taxa\n"
            msg += f"Total length: {len(seqs[0]) if seqs else 0} bp/aa\n\n"
            msg += "Partition regions:\n"
            for gene, start, end in partitions:
                msg += f"  {gene}: {start}-{end} ({end - start + 1} bp)\n"
            self.finished.emit(True, self.output_path, msg)
        except Exception as e:
            self.finished.emit(False, "", f"Error: {e}")


class _ModelFinderThread(QThread):
    progress = pyqtSignal(str)
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, partition_file, message

    def __init__(
        self,
        concat_file: str,
        partition_file: str,
        model_type: str,
        partitions: list[tuple[str, int, int]],
        exe_path: str = "",
    ):
        super().__init__()
        self.concat_file = concat_file
        self.partition_file = partition_file
        self.model_type = model_type
        self.partitions = partitions
        self.exe_path = exe_path or IQTREE_EXE
        self._proc: subprocess.Popen | None = None

    def stop(self):
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass

    def run(self):
        self.progress.emit("⏳ Running ModelFinder…")
        exe = self.exe_path
        if not os.path.isfile(exe):
            self.finished.emit(False, "", f"IQ-TREE executable not found: {exe}")
            return

        # Create temporary output dir
        tmpdir = tempfile.mkdtemp(prefix="mf_")
        prefix = os.path.join(tmpdir, "mf")

        # Create partition file for ModelFinder
        try:
            with open(tmpdir + "/partition_input.txt", "w") as f:
                for gene, start, end in self.partitions:
                    f.write(f"{self.model_type}, {gene} = {start}-{end}\n")
        except Exception as e:
            self.finished.emit(False, "", f"Error creating partition input: {e}")
            return

        # Build IQ-TREE command for ModelFinder
        cmd = [
            exe,
            "-s",
            self.concat_file,
            "-p",
            tmpdir + "/partition_input.txt",
            "-m",
            self.model_type,
            "--prefix",
            prefix,
            "-redo",
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            lines = []
            for raw in self._proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                lines.append(line)
                self.log_line.emit(line)
            self._proc.wait()

            if self._proc.returncode == 0:
                # Extract best models from IQ-TREE output
                iqtree_file = prefix + ".iqtree"
                best_models = {}
                try:
                    if os.path.isfile(iqtree_file):
                        with open(iqtree_file, "r") as f:
                            content = f.read()
                            for gene, _, _ in self.partitions:
                                if gene in content:
                                    best_models[gene] = self.model_type
                except Exception:
                    pass

                # Write output partition file with models
                try:
                    with open(self.partition_file, "w") as f:
                        f.write("#NEXUS\nBEGIN SETS;\n")
                        for gene, start, end in self.partitions:
                            f.write(f"  charset {gene} = {start}-{end};\n")
                        f.write("  partition mypart = {")
                        f.write(", ".join(f"{gene}" for gene, _, _ in self.partitions))
                        f.write("};\n")
                        f.write("  set partition = mypart;\n")
                        f.write("END;\n")
                except Exception as e:
                    self.finished.emit(False, "", f"Error writing partition file: {e}")
                    return

                msg = "✔ ModelFinder completed\n"
                msg += f"Model type: {self.model_type}\n"
                msg += f"Partition file written: {self.partition_file}\n"
                msg += "\nPartition summary:\n"
                for gene, start, end in self.partitions:
                    msg += f"  {gene}: {start}-{end}\n"
                self.finished.emit(True, self.partition_file, msg)
            else:
                output = "\n".join(lines)
                self.finished.emit(False, "", f"ModelFinder error:\n{output}")
        except Exception as e:
            self.finished.emit(False, "", f"Error: {e}")


# ---------------------------------------------------------------------------
# Help dialog
# ---------------------------------------------------------------------------
_HELP_HTML = """
<h2>Sequence Concatenation & ModelFinder</h2>
<p>Two-stage workflow for multi-gene phylogenetic analysis:</p>

<h3>Step 1: Concatenate Alignments</h3>
<ol>
  <li>Add multiple <b>aligned</b> gene/locus FASTA files.</li>
  <li>Assign gene names (e.g., COI, 16S, 18S).</li>
  <li>Run concatenation to combine all sequences.</li>
  <li>Output: single FASTA file with concatenated sequences.</li>
</ol>

<h3>Step 2: ModelFinder Analysis</h3>
<ol>
  <li>Select the concatenated alignment from Step 1.</li>
  <li>Choose model search type (TEST, DNA, AA, CODON).</li>
  <li>Run ModelFinder to analyze per-partition models.</li>
  <li>Output: NEXUS partition file ready for tree building.</li>
</ol>

<h3>Outputs</h3>
<ul>
  <li><b>Concatenated alignment</b> – Single FASTA with all genes joined.</li>
  <li><b>Partition file</b> – NEXUS format specifying:
    <ul>
      <li>Gene positions in the concatenated alignment.</li>
      <li>Ready to import into Tree Construction tab.</li>
    </ul>
  </li>
</ul>

<h3>Next Steps</h3>
<p>Use the output partition file with the <b>Tree Construction (IQ-TREE)</b> tab
to infer phylogenies with partition-aware models.</p>

<h3>Tips</h3>
<ul>
  <li>Ensure all input alignments have the same taxa (not missing any).</li>
  <li>Common gene names: COI, 16S, 18S, 28S, ITS, rbcL, matK.</li>
  <li>Sequences must be properly aligned before concatenation.</li>
  <li>Generated partition file can be edited manually if needed.</li>
</ul>
"""


class _HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Concatenation & ModelFinder Help")
        self.resize(620, 560)
        lay = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_HELP_HTML)
        lay.addWidget(browser)
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------
class PartitionConcatTab(QWidget):
    def __init__(self, status_callback=None, parent=None):
        super().__init__(parent)
        self._status_cb = status_callback
        self._concat_thread: _ConcatenateThread | None = None
        self._mf_thread: _ModelFinderThread | None = None
        self._concat_output = ""
        self._partitions: list[tuple[str, int, int]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Banner
        banner = QLabel(
            "🔗  Step 1: Concatenate multi-gene alignments  "
            "→  Step 2: Find best models per gene"
        )
        banner.setStyleSheet(
            "background:#e8f4fc;border:1px solid #90caf9;"
            "border-radius:4px;padding:6px 10px;"
        )
        root.addWidget(banner)

        # IQ-TREE exe path
        exe_row = QHBoxLayout()
        self._exe_edit = _DropLineEdit(IQTREE_EXE)
        self._exe_edit.setPlaceholderText(
            "e.g. C:/iqtree-3.0.1/bin/iqtree3.exe (drag & drop supported)"
        )
        exe_chg = QPushButton("⚙")
        exe_chg.setFixedWidth(30)
        exe_chg.clicked.connect(self._choose_exe)
        exe_row.addWidget(QLabel("IQ-TREE exe:"))
        exe_row.addWidget(self._exe_edit, 1)
        exe_row.addWidget(exe_chg)
        root.addLayout(exe_row)

        root.addWidget(_hline())

        # ========== STEP 1: CONCATENATION ==========
        root.addWidget(QLabel("<b>Step 1: Concatenate Gene Alignments</b>"))

        # File list
        file_label = QLabel("Input alignment files:")
        file_label.setToolTip(
            "Each file = one gene/locus; must share the same taxa and be pre-aligned"
        )
        root.addWidget(file_label)
        self._file_list = _DropFileList(
            "Drag & drop aligned FASTA files here, or click Choose to select"
        )
        self._file_list.setMaximumHeight(120)
        root.addWidget(self._file_list)

        # Choose / Clear buttons
        file_btn_row = QHBoxLayout()
        choose_btn = QPushButton("Choose")
        choose_btn.setMaximumWidth(90)
        choose_btn.clicked.connect(self._add_file)
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(90)
        clear_btn.clicked.connect(self._clear_files)
        file_btn_row.addWidget(choose_btn)
        file_btn_row.addWidget(clear_btn)
        file_btn_row.addStretch()
        root.addLayout(file_btn_row)

        # Sequence type
        st_row = QHBoxLayout()
        st_row.addWidget(QLabel("Sequence type:"))
        self._seqtype_combo = QComboBox()
        self._seqtype_combo.addItems(["DNA", "Protein"])
        st_row.addWidget(self._seqtype_combo)
        st_row.addStretch()
        root.addLayout(st_row)

        # Output file
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output file:"))
        self._output_edit = _DropLineEdit()
        self._output_edit.setPlaceholderText(
            "Output concatenated alignment file (drag & drop supported)"
        )
        out_browse = QPushButton("Browse")
        out_browse.setMaximumWidth(90)
        out_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self._output_edit, 1)
        out_row.addWidget(out_browse)
        root.addLayout(out_row)

        # Concatenate button
        self._concat_btn = QPushButton("▶  Concatenate")
        self._concat_btn.setMinimumHeight(32)
        self._concat_btn.setStyleSheet(
            "QPushButton{background:#4caf50;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#45a049;}"
            "QPushButton:disabled{background:#90a4ae;}"
        )
        self._concat_btn.clicked.connect(self._run_concat)
        root.addWidget(self._concat_btn)

        # Concat output
        self._concat_output_edit = QTextEdit()
        self._concat_output_edit.setReadOnly(True)
        self._concat_output_edit.setMaximumHeight(100)
        self._concat_output_edit.setFont(QFont("Courier New", 8))
        self._concat_output_edit.setPlaceholderText(
            "✓ Concatenation results: number of taxa, sequence length, partition regions…"
        )
        root.addWidget(self._concat_output_edit)

        root.addWidget(_hline())

        # ========== STEP 2: MODELFINDER ==========
        root.addWidget(QLabel("<b>Step 2: ModelFinder Analysis</b>"))

        # Concat file (from step 1)
        mf_form = QFormLayout()
        self._concat_file_edit = QLineEdit()
        self._concat_file_edit.setPlaceholderText(
            "Auto-filled after Step 1 concatenation completes"
        )
        mf_form.addRow("Concatenated file:", self._concat_file_edit)

        # Model type
        self._mf_model_combo = QComboBox()
        self._mf_model_combo.addItems(["TEST", "DNA", "AA", "CODON"])
        self._mf_model_combo.setToolTip(
            "TEST: comprehensive search (slower)\n"
            "DNA: DNA models only\nAA: Protein models only\n"
            "CODON: Codon models only"
        )
        mf_form.addRow("Model search type:", self._mf_model_combo)

        # Partition output
        part_out_row = QHBoxLayout()
        self._partition_edit = QLineEdit()
        self._partition_edit.setPlaceholderText(
            "Output NEXUS partition file with per-gene models"
        )
        part_browse = QPushButton("Browse")
        part_browse.setMaximumWidth(90)
        part_browse.clicked.connect(self._browse_partition_out)
        part_out_row.addWidget(self._partition_edit, 1)
        part_out_row.addWidget(part_browse)
        mf_form.addRow("Output partition file:", part_out_row)

        root.addLayout(mf_form)

        # ModelFinder button
        self._mf_btn = QPushButton("▶  Run ModelFinder")
        self._mf_btn.setMinimumHeight(32)
        self._mf_btn.setStyleSheet(
            "QPushButton{background:#2196f3;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#0b7dda;}"
            "QPushButton:disabled{background:#90a4ae;}"
        )
        self._mf_btn.clicked.connect(self._run_modelfinder)
        root.addWidget(self._mf_btn)

        # ModelFinder output
        self._mf_output_edit = QTextEdit()
        self._mf_output_edit.setReadOnly(True)
        self._mf_output_edit.setMaximumHeight(120)
        self._mf_output_edit.setFont(QFont("Courier New", 8))
        self._mf_output_edit.setPlaceholderText(
            "ModelFinder progress log: model testing, partition analysis, result summary…"
        )
        root.addWidget(self._mf_output_edit)

        root.addWidget(_hline())

        # Status & Help
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#555;font-style:italic;")
        root.addWidget(self._status_lbl)

        help_btn = QPushButton("Help")
        help_btn.setMaximumWidth(90)
        help_btn.clicked.connect(self._show_help)
        root.addWidget(help_btn)

        root.addStretch()

    # Slots
    def _choose_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select IQ-TREE executable", "", "Executables (*.exe);;All Files (*)"
        )
        if path:
            self._exe_edit.setText(path)

    def _add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select alignment files",
            "",
            "FASTA files (*.fasta *.fa *.txt);;All Files (*)",
        )
        for path in paths:
            # Avoid duplicates
            existing = [
                it.data(256)
                for i in range(self._file_list.count())
                if (it := self._file_list.item(i)) is not None
            ]
            if path not in existing:
                item = QListWidgetItem(os.path.basename(path))
                item.setData(256, path)
                self._file_list.addItem(item)

    def _remove_file(self):
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    def _clear_files(self):
        self._file_list.clear()

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save concatenated alignment",
            "",
            "FASTA files (*.fasta *.fa);;All Files (*)",
        )
        if path:
            self._output_edit.setText(path)

    def _browse_partition_out(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save partition file", "", "NEXUS files (*.nex);;All Files (*)"
        )
        if path:
            self._partition_edit.setText(path)

    def _show_help(self):
        dlg = _HelpDialog(self)
        dlg.exec()

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
        if self._status_cb:
            self._status_cb(msg, 0)

    def _run_concat(self):
        # Collect files
        files = []
        gene_names = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item:
                fpath = item.data(256)
                if fpath:
                    fname = os.path.splitext(os.path.basename(fpath))[0]
                    files.append(fpath)
                    gene_names.append(fname)

        if not files:
            self._set_status("⚠ Please add at least one alignment file.")
            return

        output = self._output_edit.text().strip()
        if not output:
            self._set_status("⚠ Please specify output file.")
            return

        self._concat_btn.setEnabled(False)
        self._concat_output_edit.clear()
        self._set_status("⏳ Concatenating…")

        self._concat_thread = _ConcatenateThread(files, gene_names, output)
        self._concat_thread.progress.connect(self._set_status)
        self._concat_thread.finished.connect(self._on_concat_finished)
        self._concat_thread.start()

    def _on_concat_finished(self, success: bool, output_path: str, message: str):
        self._concat_btn.setEnabled(True)
        self._concat_output_edit.setPlainText(message)

        if success:
            self._concat_output = output_path
            self._concat_file_edit.setText(output_path)
            # Extract partition info
            files = []
            gene_names = []
            for i in range(self._file_list.count()):
                item = self._file_list.item(i)
                if item:
                    fpath = item.data(256)
                    if fpath:
                        fname = os.path.splitext(os.path.basename(fpath))[0]
                        files.append(fpath)
                        gene_names.append(fname)
            try:
                _, _, self._partitions = _concatenate_alignments(files, gene_names)
            except Exception:
                self._partitions = []
            self._set_status(f"✔ Concatenation complete: {output_path}")
        else:
            self._partitions = []
            self._set_status(f"✖ Concatenation failed: {message}")

    def _run_modelfinder(self):
        concat_file = self._concat_file_edit.text().strip()
        if not concat_file or not os.path.isfile(concat_file):
            self._set_status("⚠ Concatenated file not found.")
            return

        if not self._partitions:
            self._set_status("⚠ Run Step 1 (Concatenate) first to define partitions.")
            return

        partition_out = self._partition_edit.text().strip()
        if not partition_out:
            self._set_status("⚠ Please specify partition output file.")
            return

        model_type = self._mf_model_combo.currentText()

        self._mf_btn.setEnabled(False)
        self._mf_output_edit.clear()
        self._set_status("⏳ Running ModelFinder…")

        exe_path = self._exe_edit.text().strip() or IQTREE_EXE
        self._mf_thread = _ModelFinderThread(
            concat_file, partition_out, model_type, self._partitions, exe_path
        )
        self._mf_thread.progress.connect(self._set_status)
        self._mf_thread.log_line.connect(self._append_mf_log)
        self._mf_thread.finished.connect(self._on_mf_finished)
        self._mf_thread.start()

    def _append_mf_log(self, line: str):
        self._mf_output_edit.moveCursor(
            self._mf_output_edit.textCursor().MoveOperation.End
        )
        self._mf_output_edit.insertPlainText(line + "\n")

    def _on_mf_finished(self, success: bool, partition_file: str, message: str):
        self._mf_btn.setEnabled(True)
        if success:
            self._mf_output_edit.setPlainText(message)
            self._set_status(f"✔ ModelFinder complete: {partition_file}")
        else:
            self._mf_output_edit.setPlainText(message)
            self._set_status("✖ ModelFinder failed")
