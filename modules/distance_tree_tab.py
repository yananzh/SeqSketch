"""
Distance Matrix & NJ Tree Tab
==============================
Compute pairwise distance matrix from a FASTA alignment and build a
Neighbor-Joining / UPGMA tree using BioPython.  No external executables
required.

Powered by Bio.Phylo.TreeConstruction.
"""

import os
from io import StringIO

from Bio import AlignIO, Phylo
from Bio.Phylo.TreeConstruction import DistanceCalculator, DistanceTreeConstructor
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, apply_log_viewer_style, validate_input_path


# ---------------------------------------------------------------------------
# Drag-and-drop QLineEdit
# ---------------------------------------------------------------------------
class _DropLineEdit(QLineEdit):
    """QLineEdit that accepts file drops."""

    fileDropped = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0:
            mime = a0.mimeData()
            if mime and mime.hasUrls():
                a0.acceptProposedAction()
                return
        super().dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0:
            mime = a0.mimeData()
            if mime:
                urls = mime.urls()
                if urls:
                    path = urls[0].toLocalFile()
                    self.setText(path)
                    self.fileDropped.emit(path)
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ---------------------------------------------------------------------------
# Horizontal separator helper
# ---------------------------------------------------------------------------
def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


# ---------------------------------------------------------------------------
# Worker: compute distance matrix and build tree
# ---------------------------------------------------------------------------
class _DistanceTreeWorker(QThread):
    """Compute pairwise distance matrix and NJ / UPGMA tree in background."""

    finished_ok = pyqtSignal(dict)  # {matrix, names, newick, n_taxa}
    finished_err = pyqtSignal(str)

    def __init__(self, input_path: str, model: str, method: str):
        super().__init__()
        self._input_path = input_path
        self._model = model
        self._method = method

    def run(self):
        try:
            # ── read alignment ────────────────────────────────────
            fmt = _detect_alignment_format(self._input_path)
            alignment = AlignIO.read(self._input_path, fmt)

            n_taxa = len(alignment)
            if n_taxa < 3:
                self.finished_err.emit(
                    f"Need at least 3 sequences, found {n_taxa}."
                )
                return

            # ── calculate distance matrix ─────────────────────────
            calculator = DistanceCalculator(self._model)
            dm = calculator.get_distance(alignment)

            names = list(dm.names)

            # Build symmetric n×n matrix using dm[i][j] accessor
            # (handles lower-triangular internal storage correctly)
            matrix = []
            for i in range(n_taxa):
                row = [dm[i][j] for j in range(n_taxa)]
                matrix.append(row)

            # ── build tree ────────────────────────────────────────
            constructor = DistanceTreeConstructor()
            if self._method == "nj":
                tree = constructor.nj(dm)
            else:
                tree = constructor.upgma(dm)

            buf = StringIO()
            Phylo.write(tree, buf, "newick")
            newick_str = buf.getvalue().strip()

            self.finished_ok.emit({
                "matrix": matrix,
                "names": names,
                "newick": newick_str,
                "n_taxa": n_taxa,
            })
        except Exception as exc:
            import traceback

            tb = traceback.format_exc()
            self.finished_err.emit(f"{exc}\n{tb}")


def _detect_alignment_format(path: str) -> str:
    """Guess alignment format from file extension."""
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".fasta": "fasta", ".fa": "fasta", ".fas": "fasta",
        ".fna": "fasta", ".ffn": "fasta", ".faa": "fasta",
        ".phy": "phylip", ".phylip": "phylip",
        ".nex": "nexus", ".nxs": "nexus",
        ".clustal": "clustal", ".aln": "clustal",
        ".sto": "stockholm",
    }
    return mapping.get(ext, "fasta")


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------
class DistanceTreeTab(BaseTabWidget):
    def __init__(self, status_callback=None, parent=None):
        super().__init__("Distance Matrix & NJ Tree", "file")
        self._thread: _DistanceTreeWorker | None = None
        self._matrix_data = None   # latest result
        self._newick_str = ""
        self._names = []
        self._build_ui()
        self._connect_signals()
        self.show_status(self.tr("Ready — load a FASTA alignment and click Compute"))

    # ── UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        lbl_w = 120

        # ── Input group ─────────────────────────────────────────────
        grp_in = QGroupBox(self.tr("Input"))
        gl = QVBoxLayout(grp_in)
        gl.setSpacing(8)

        # file row
        fr = QHBoxLayout()
        lbl_file = QLabel(self.tr("Alignment file:"))
        lbl_file.setFixedWidth(lbl_w)
        fr.addWidget(lbl_file)
        self._file_edit = _DropLineEdit()
        self._file_edit.setPlaceholderText(
            self.tr("Select or drag & drop a FASTA alignment...")
        )
        fr.addWidget(self._file_edit, 1)
        browse_btn = QPushButton(self.tr("Browse"))
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_input)
        fr.addWidget(browse_btn)
        gl.addLayout(fr)

        # model + method row
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel(self.tr("Model:")))
        self._model_combo = QComboBox()
        self._model_combo.addItems(["identity", "blastn"])
        self._model_combo.setMinimumWidth(100)
        self._model_combo.setToolTip(
            self.tr("identity: simple p-distance | blastn: BLAST identity-based")
        )
        opt_row.addWidget(self._model_combo)
        opt_row.addSpacing(20)
        opt_row.addWidget(QLabel(self.tr("Method:")))
        self._method_combo = QComboBox()
        self._method_combo.addItems(["nj", "upgma"])
        self._method_combo.setMinimumWidth(100)
        self._method_combo.setToolTip(
            self.tr("nj: Neighbor-Joining (fast, accurate) | upgma: UPGMA (ultrametric)")
        )
        opt_row.addWidget(self._method_combo)
        opt_row.addStretch()
        gl.addLayout(opt_row)
        self.content_area.addWidget(grp_in)

        # ── Output group ────────────────────────────────────────────
        grp_out = QGroupBox(self.tr("Output"))
        ol = QVBoxLayout(grp_out)
        ol.setSpacing(8)

        out_row = QHBoxLayout()
        lbl_out = QLabel(self.tr("Tree file (.nwk):"))
        lbl_out.setFixedWidth(lbl_w)
        out_row.addWidget(lbl_out)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText(
            self.tr("Auto-generated from input name, or choose manually...")
        )
        out_row.addWidget(self._out_edit, 1)
        save_btn = QPushButton(self.tr("Save As"))
        save_btn.setFixedWidth(90)
        save_btn.clicked.connect(self._browse_output)
        out_row.addWidget(save_btn)
        ol.addLayout(out_row)
        self.content_area.addWidget(grp_out)

        # ── Distance matrix table ───────────────────────────────────
        matrix_grp = QGroupBox(self.tr("Distance Matrix"))
        ml = QVBoxLayout(matrix_grp)
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Monospace for alignment
        self._table.setStyleSheet(
            "QTableWidget { font-family: 'Cascadia Mono', 'Consolas', monospace; }"
        )
        ml.addWidget(self._table)
        self.content_area.addWidget(matrix_grp)

        self.content_area.addStretch()

        # ── Action buttons in status bar, left of Help ─────────
        self._compute_btn = QPushButton(self.tr("Compute"))
        self._compute_btn.setFixedWidth(100)
        self._compute_btn.clicked.connect(self._compute)

        self._export_csv_btn = QPushButton(self.tr("Export Matrix"))
        self._export_csv_btn.setFixedWidth(160)
        self._export_csv_btn.setEnabled(False)
        self._export_csv_btn.clicked.connect(self._export_csv)

        self._clear_btn = QPushButton(self.tr("Clear"))
        self._clear_btn.setFixedWidth(80)
        self._clear_btn.clicked.connect(self._clear_all)

        # Insert before Help button (rightmost in status_layout)
        self.status_layout.insertWidget(
            self.status_layout.count() - 1, self._clear_btn
        )
        self.status_layout.insertWidget(
            self.status_layout.count() - 1, self._export_csv_btn
        )
        self.status_layout.insertWidget(
            self.status_layout.count() - 1, self._compute_btn
        )

    def _connect_signals(self):
        self._file_edit.fileDropped.connect(self._on_file_dropped)

    # ── Slots ───────────────────────────────────────────────────────
    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select FASTA Alignment"),
            "",
            self.tr(
                "Alignment Files (*.fasta *.fa *.fas *.fna *.ffn *.faa "
                "*.phy *.phylip *.nex *.nxs *.aln *.clustal *.sto);;All Files (*)"
            ),
        )
        if path:
            self._file_edit.setText(path)
            # Auto-suggest output
            if not self._out_edit.text().strip():
                base, _ = os.path.splitext(path)
                self._out_edit.setText(base + "_tree.nwk")

    def _on_file_dropped(self, path: str):
        if not self._out_edit.text().strip():
            base, _ = os.path.splitext(path)
            self._out_edit.setText(base + "_tree.nwk")

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Tree File"),
            self._out_edit.text() or "tree.nwk",
            self.tr("Newick Files (*.nwk *.newick *.treefile *.tre);;All Files (*)"),
        )
        if path:
            self._out_edit.setText(path)

    def _compute(self):
        input_path = self._file_edit.text().strip()
        valid, err = validate_input_path(input_path)
        if not valid:
            self.log_message(err, "ERROR")
            self.show_status(err)
            return

        output_path = self._out_edit.text().strip()
        if not output_path:
            # Auto-generate
            base, _ = os.path.splitext(input_path)
            output_path = base + "_tree.nwk"
            self._out_edit.setText(output_path)

        model = self._model_combo.currentText()
        method = self._method_combo.currentText()

        self._set_running(True)
        self.log_message(
            self.tr(f"Computing {method.upper()} tree ({model}) from {input_path} ...")
        )
        self.show_status(self.tr("Computing distance matrix..."))

        self._thread = _DistanceTreeWorker(input_path, model, method)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_result(self, data: dict):
        self._matrix_data = data["matrix"]
        self._names = data["names"]
        self._newick_str = data["newick"]
        n_taxa = data["n_taxa"]

        # Populate table
        self._populate_table(data["matrix"], data["names"])

        # Save tree to output file
        output_path = self._out_edit.text().strip()
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self._newick_str + "\n")
            self.log_message(
                self.tr(f"✔ Tree saved → {output_path}  ({n_taxa} taxa)")
            )
            self.show_status(
                self.tr(f"✔ {self._method_combo.currentText().upper()} tree saved ({n_taxa} taxa)")
            )
        except Exception as exc:
            self.log_message(self.tr(f"✖ Failed to save tree: {exc}"), "ERROR")
            self.show_status(self.tr("Tree computed but save failed"))

        self._export_csv_btn.setEnabled(True)
        self._set_running(False)
        self._thread = None

    def _on_error(self, msg: str):
        self.log_message(f"✖ {msg}", "ERROR")
        self.show_status(self.tr(f"Error: {msg}"))
        self._set_running(False)
        self._thread = None

    def _populate_table(self, matrix, names):
        n = len(names)
        self._table.clear()
        self._table.setRowCount(n)
        self._table.setColumnCount(n)
        self._table.setHorizontalHeaderLabels(names)
        self._table.setVerticalHeaderLabels(names)

        # Compute max off-diagonal distance for color scaling
        max_dist = 0.0
        for i in range(n):
            for j in range(n):
                if i != j:
                    max_dist = max(max_dist, matrix[i][j])
        if max_dist == 0.0:
            max_dist = 1.0  # avoid division by zero

        for i in range(n):
            for j in range(n):
                val = matrix[i][j]
                item = QTableWidgetItem(f"{val:.4f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                # Color-code off-diagonal only; diagonal stays unstyled
                if i != j:
                    intensity = int(255 * (1 - val / max_dist))
                    if intensity > 250:
                        color = Qt.GlobalColor.white
                    elif intensity > 200:
                        color = Qt.GlobalColor.lightGray
                    elif intensity > 120:
                        color = Qt.GlobalColor.gray
                    else:
                        color = Qt.GlobalColor.darkGray
                    item.setBackground(color)
                self._table.setItem(i, j, item)

        self._table.resizeColumnsToContents()
        self._table.resizeRowsToContents()

    def _export_csv(self):
        if not self._matrix_data:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Distance Matrix"),
            "distance_matrix.csv",
            self.tr("CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"),
        )
        if not path:
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".xlsx":
                import pandas as pd

                df = pd.DataFrame(
                    self._matrix_data,
                    index=self._names,
                    columns=self._names,
                )
                df.to_excel(path, float_format="%.6f")
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("taxa," + ",".join(self._names) + "\n")
                    for i, name in enumerate(self._names):
                        f.write(name + "," + ",".join(
                            f"{v:.6f}" for v in self._matrix_data[i]
                        ) + "\n")
            self.log_message(self.tr(f"✔ Matrix exported → {path}"))
            self.show_status(self.tr("Matrix exported"))
        except Exception as exc:
            self.log_message(self.tr(f"✖ Export failed: {exc}"), "ERROR")

    def _clear_all(self):
        self._file_edit.clear()
        self._out_edit.clear()
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._matrix_data = None
        self._newick_str = ""
        self._names = []
        self._export_csv_btn.setEnabled(False)
        self.log_area.clear()
        self.show_status(self.tr("Cleared"))

    def _set_running(self, running: bool):
        self._compute_btn.setEnabled(not running)
        self._file_edit.setEnabled(not running)

    # ── Help ────────────────────────────────────────────────────────
    def show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Distance Matrix & NJ Tree — Help"))
        dlg.resize(640, 560)
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
<h2>Distance Matrix &amp; NJ Tree</h2>

<p><b>What does this tool do?</b><br>
Computes a pairwise <b>distance matrix</b> from a multiple sequence alignment,
then builds a <b>Neighbor-Joining</b> or <b>UPGMA</b> phylogenetic tree.
Powered by <b>BioPython</b> — no external binaries needed.</p>

<h3>Quick Start</h3>
<ol>
  <li><b>Load</b> a FASTA (or PHYLIP, NEXUS, CLUSTAL) alignment file.</li>
  <li>Choose a <b>distance model</b> and <b>tree method</b>.</li>
  <li>Set the output <b>tree file (.nwk)</b> path (auto-suggested).</li>
  <li>Click <b>Compute</b> — the matrix appears below, tree saved to file.</li>
  <li>Use <b>Export Matrix (CSV)</b> to save the distance table.</li>
</ol>

<h3>Distance Models</h3>
<table>
  <tr><td><b>identity</b></td><td>&mdash; simple p-distance (fraction of differing sites)</td></tr>
  <tr><td><b>blastn</b></td><td>&mdash; BLAST identity-based distance (DNA only)</td></tr>
</table>

<h3>Tree Methods</h3>
<table>
  <tr><td><b>NJ</b></td><td>&mdash; Neighbor-Joining: fast, accurate, widely used</td></tr>
  <tr><td><b>UPGMA</b></td><td>&mdash; Unweighted Pair Group Method: assumes molecular clock (ultrametric)</td></tr>
</table>

<h3>Supported Input Formats</h3>
<table>
  <tr><td><b>FASTA</b></td><td><code>.fasta .fa .fas .fna .ffn .faa</code></td></tr>
  <tr><td><b>PHYLIP</b></td><td><code>.phy .phylip</code></td></tr>
  <tr><td><b>NEXUS</b></td><td><code>.nex .nxs</code></td></tr>
  <tr><td><b>CLUSTAL</b></td><td><code>.aln .clustal</code></td></tr>
  <tr><td><b>Stockholm</b></td><td><code>.sto</code></td></tr>
</table>

<h3>Output</h3>
<ul>
  <li><b>Tree file</b> &mdash; Newick format (.nwk), ready for visualization in
  <b>Simple Tree Visualization (Phytreeviz)</b> or IQ-TREE.</li>
  <li><b>Distance Matrix</b> &mdash; displayed in the table; export to CSV for
  heatmap plotting or external analysis.</li>
</ul>

<h3>Tips</h3>
<ul>
  <li>Files can be <b>dragged &amp; dropped</b> directly into the input field.</li>
  <li>For large alignments (100+ taxa) the computation may take a few seconds.</li>
  <li>NJ trees are unrooted by default; use <b>Simple Tree Visualization</b> to
  re-root your tree.</li>
  <li>For maximum-likelihood trees, see <b>ML Tree Construction (IQ-TREE)</b>.</li>
</ul>
""")
