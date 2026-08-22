"""
Distance Tree Construction Tab
==============================
Compute pairwise distance matrix from a FASTA alignment and build a
Neighbor-Joining / UPGMA tree using BioPython.  No external executables
required.

Powered by Bio.Phylo.TreeConstruction.
"""

import math
import os
from io import StringIO

import numpy as np
from Bio import AlignIO, Phylo
from Bio.Phylo.TreeConstruction import DistanceCalculator, DistanceTreeConstructor
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.common_components import (
    BaseTabWidget,
    unify_status_button_sizes,
    validate_input_path,
)

# ── Distance model presets ────────────────────────────────────────────────
_DNA_MODELS = [
    ("p-distance (identity)", "identity"),
    ("Jukes-Cantor (JC69)", "jc69"),
    ("Kimura 2-parameter (K80)", "k80"),
]

_AA_MODELS = [
    ("BLOSUM62", "blosum62"),
    ("Dayhoff", "dayhoff"),
    ("p-distance (identity)", "identity"),
]


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
# Worker: compute distance matrix and build tree
# ---------------------------------------------------------------------------
class _DistanceTreeWorker(QThread):
    """Compute pairwise distance matrix and NJ / UPGMA tree in background."""

    finished_ok = pyqtSignal(dict)  # {matrix, names, newick, n_taxa, n_bootstrap}
    finished_err = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total (for bootstrap)

    def __init__(self, input_path: str, model: str, method: str, n_bootstrap: int = 0):
        super().__init__()
        self._input_path = input_path
        self._model = model
        self._method = method
        self._n_bootstrap = n_bootstrap

    def run(self):
        try:
            # ── read alignment ────────────────────────────────────
            fmt = _detect_alignment_format(self._input_path)
            alignment = AlignIO.read(self._input_path, fmt)

            n_taxa = len(alignment)
            if n_taxa < 3:
                self.finished_err.emit(f"Need at least 3 sequences, found {n_taxa}.")
                return

            # ── calculate distance matrix ─────────────────────────
            dm = _make_distance_matrix(alignment, self._model)

            names = list(dm.names)

            # Build symmetric n×n matrix using dm[i][j] accessor
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

            n_bootstrap_done = 0
            warning = ""

            # ── bootstrap ─────────────────────────────────────────
            if self._n_bootstrap > 0:
                if not _HAS_BOOTSTRAP:
                    warning = (
                        "Bootstrap support is unavailable (Biopython's "
                        "get_support is missing); the tree was built without it."
                    )
                else:
                    n_cols = alignment.get_alignment_length()
                    # Convert alignment to 2D char array for fast column resampling
                    aln_array = np.array([list(str(rec.seq)) for rec in alignment])
                    bootstrap_trees = []
                    for i in range(self._n_bootstrap):
                        indices = np.random.randint(0, n_cols, size=n_cols)
                        boot_cols = aln_array[:, indices]
                        # Rebuild bootstrap alignment in memory
                        from Bio.Align import MultipleSeqAlignment
                        from Bio.Seq import Seq
                        from Bio.SeqRecord import SeqRecord

                        boot_records = []
                        for row_idx, rec in enumerate(alignment):
                            boot_seq = "".join(boot_cols[row_idx])
                            boot_records.append(
                                SeqRecord(
                                    Seq(boot_seq),
                                    id=rec.id,
                                    description=rec.description,
                                )
                            )
                        boot_aln = MultipleSeqAlignment(boot_records)

                        dm_boot = _make_distance_matrix(boot_aln, self._model)
                        if self._method == "nj":
                            tree_boot = constructor.nj(dm_boot)
                        else:
                            tree_boot = constructor.upgma(dm_boot)
                        bootstrap_trees.append(tree_boot)
                        self.progress.emit(i + 1, self._n_bootstrap)

                    # Annotate main tree with bootstrap support values
                    tree = _get_support(tree, bootstrap_trees)
                    n_bootstrap_done = self._n_bootstrap

            buf = StringIO()
            Phylo.write(tree, buf, "newick")
            newick_str = buf.getvalue().strip()

            # Convert BioPython node-name bootstrap to standard Newick:
            #   )Inner2100.00:0.18  →  )100.00:0.18
            import re

            newick_str = re.sub(r"\)Inner\d+?(\d+\.\d+):", r")\1:", newick_str)

            self.finished_ok.emit({
                "matrix": matrix,
                "names": names,
                "newick": newick_str,
                "n_taxa": n_taxa,
                "n_bootstrap": n_bootstrap_done,
                "warning": warning,
            })
        except Exception as exc:
            self.finished_err.emit(str(exc))


def _detect_alignment_format(path: str) -> str:
    """Guess alignment format from file extension."""
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".fasta": "fasta",
        ".fa": "fasta",
        ".fas": "fasta",
        ".fna": "fasta",
        ".ffn": "fasta",
        ".faa": "fasta",
        ".phy": "phylip",
        ".phylip": "phylip",
        ".nex": "nexus",
        ".nxs": "nexus",
        ".clustal": "clustal",
        ".aln": "clustal",
        ".sto": "stockholm",
    }
    return mapping.get(ext, "fasta")


def _detect_seq_type(path: str) -> str:
    """Detect DNA vs Protein from the first sequence in an alignment file."""
    dna_chars = set("ACGTRYSWKMBDHVNU")
    try:
        fmt = _detect_alignment_format(path)
        alignment = AlignIO.read(path, fmt)
        for rec in alignment:
            seq_str = str(rec.seq).replace("-", "").replace(".", "").upper()
            if not seq_str:
                continue
            dna_count = sum(1 for c in seq_str if c in dna_chars)
            return "DNA" if dna_count / len(seq_str) >= 0.85 else "AA"
    except (OSError, ValueError, StopIteration):
        pass
    return "DNA"


# ── Evolutionary distance models (DNA) ────────────────────────────────────
_DNA_BASES = set("ACGTU")
_PURINES = set("AG")
_PYRIMIDINES = set("CTU")


def _dna_distance_matrix(alignment, model: str):
    """Compute a Jukes-Cantor (``jc69``) or Kimura 2-parameter (``k80``)
    distance matrix directly from an aligned matrix.

    Only sites where both sequences have a concrete base (A/C/G/T/U) are
    compared (pairwise deletion of gaps and ambiguous codes). Distances that
    exceed the model's saturation point are capped at 999.
    """
    from Bio.Phylo.TreeConstruction import DistanceMatrix

    names = [rec.id for rec in alignment]
    rows = []
    for i in range(len(names)):
        seq_i = str(alignment[i].seq).upper()
        row = []
        for j in range(i + 1):
            if i == j:
                row.append(0.0)
                continue
            seq_j = str(alignment[j].seq).upper()
            comparable = differences = transitions = transversions = 0
            for a, b in zip(seq_i, seq_j):
                if a not in _DNA_BASES or b not in _DNA_BASES:
                    continue
                comparable += 1
                if a == b:
                    continue
                differences += 1
                if (a in _PURINES and b in _PURINES) or (
                    a in _PYRIMIDINES and b in _PYRIMIDINES
                ):
                    transitions += 1
                else:
                    transversions += 1
            if comparable == 0:
                row.append(0.0)
                continue
            if model == "jc69":
                p = differences / comparable
                arg = 1.0 - 4.0 / 3.0 * p
                row.append(-0.75 * math.log(arg) if arg > 0 else 999.0)
            else:  # k80
                p_trans = transitions / comparable
                p_transv = transversions / comparable
                arg1 = 1.0 - 2.0 * p_trans - p_transv
                arg2 = 1.0 - 2.0 * p_transv
                if arg1 <= 0 or arg2 <= 0:
                    row.append(999.0)
                else:
                    row.append(-0.5 * math.log(arg1) - 0.25 * math.log(arg2))
        rows.append(row)
    return DistanceMatrix(names, rows)


def _make_distance_matrix(alignment, model: str):
    """Compute a Biopython DistanceMatrix for ``model``.

    ``jc69`` / ``k80`` are computed directly; all other models (including the
    protein matrices) are delegated to Biopython's ``DistanceCalculator``.
    """
    if model in ("jc69", "k80"):
        return _dna_distance_matrix(alignment, model)
    return DistanceCalculator(model).get_distance(alignment)


# ── Bootstrap consensus (optional — BioPython ≥ 1.58) ─────────────────────
try:
    from Bio.Phylo.Consensus import get_support as _get_support

    _HAS_BOOTSTRAP = True
except ImportError:
    _HAS_BOOTSTRAP = False


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------
class DistanceTreeTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Distance Tree Construction", "file")
        self._thread: _DistanceTreeWorker | None = None
        self._matrix_data = None  # latest result
        self._newick_str = ""
        self._names = []
        self._last_treefile = ""
        self._build_ui()
        self._connect_signals()
        self.show_status(self.tr("Ready — load a FASTA alignment and click Run"))

    # ── UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        lbl_w = 120

        # ── Input group ─────────────────────────────────────────────
        grp_in = QGroupBox(self.tr("Input and Method"))
        gl = QVBoxLayout(grp_in)
        gl.setSpacing(8)

        # file row
        fr = QHBoxLayout()
        lbl_file = QLabel(self.tr("Alignment file:"))
        lbl_file.setFixedWidth(lbl_w)
        fr.addWidget(lbl_file)
        self._file_edit = _DropLineEdit()
        self._file_edit.setPlaceholderText(self.tr("Select or drag & drop a FASTA alignment..."))
        fr.addWidget(self._file_edit, 1)
        self._example_btn = QPushButton(self.tr("Example"))
        self._example_btn.setToolTip(
            self.tr("Load bundled example alignment (csrA_pro_mafft.fasta)")
        )
        self._example_btn.clicked.connect(self._load_example)
        fr.addWidget(self._example_btn)
        self._browse_btn = QPushButton(self.tr("Browse"))
        self._browse_btn.setFixedWidth(90)
        self._browse_btn.clicked.connect(self._browse_input)
        fr.addWidget(self._browse_btn)
        gl.addLayout(fr)

        # model + method + bootstrap row
        opt_row = QHBoxLayout()
        lbl_model = QLabel(self.tr("Model Selection:"))
        lbl_model.setFixedWidth(lbl_w)
        opt_row.addWidget(lbl_model)
        self._model_combo = QComboBox()
        for display, data in _DNA_MODELS:
            self._model_combo.addItem(self.tr(display), data)
        self._model_combo.setMinimumWidth(220)
        self._model_combo.setToolTip(
            self.tr(
                "p-distance: fraction of differing sites  |  JC69: Jukes-Cantor correction  |  "
                "K80: Kimura 2-parameter (transitions vs transversions)\n"
                "First time? NJ + p-distance is a safe start."
            )
        )
        opt_row.addWidget(self._model_combo)
        opt_row.addSpacing(20)
        opt_row.addWidget(QLabel(self.tr("Method:")))
        self._method_combo = QComboBox()
        self._method_combo.addItem("NJ", "nj")
        self._method_combo.addItem("UPGMA", "upgma")
        self._method_combo.setMinimumWidth(100)
        self._method_combo.setToolTip(
            self.tr(
                "nj: Neighbor-Joining (fast, accurate, no clock assumption)  |  "
                "upgma: UPGMA (assumes a molecular clock — check before using)"
            )
        )
        opt_row.addWidget(self._method_combo)
        opt_row.addSpacing(20)
        opt_row.addWidget(QLabel(self.tr("Bootstrap:")))
        self._bootstrap_spin = QSpinBox()
        self._bootstrap_spin.setRange(0, 10000)
        self._bootstrap_spin.setSingleStep(100)
        self._bootstrap_spin.setValue(1000)
        self._bootstrap_spin.setSpecialValueText(self.tr("Off"))
        self._bootstrap_spin.setToolTip(
            self.tr("Number of bootstrap replicates (0 = off). 100–1000 recommended.")
        )
        opt_row.addWidget(self._bootstrap_spin)
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
        self._save_btn = QPushButton(self.tr("Browse"))
        self._save_btn.setFixedWidth(90)
        self._save_btn.clicked.connect(self._browse_output)
        out_row.addWidget(self._save_btn)
        ol.addLayout(out_row)
        self.content_area.addWidget(grp_out)

        # ── Distance matrix table ───────────────────────────────────
        matrix_grp = QGroupBox(self.tr("Distance Matrix"))
        ml = QVBoxLayout(matrix_grp)
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Monospace for alignment
        self._table.setStyleSheet(
            "QTableWidget { font-family: 'Cascadia Mono', 'Consolas', monospace; }"
        )
        ml.addWidget(self._table)
        self.content_area.addWidget(matrix_grp)

        self.content_area.addStretch()

        # ── Action buttons in status bar, left of Help ─────────
        self._run_btn = QPushButton(self.tr("Run"))
        self._run_btn.clicked.connect(self._compute)

        self._view_tree_btn = QPushButton(self.tr("View Tree"))
        self._view_tree_btn.setVisible(False)
        self._view_tree_btn.clicked.connect(self._open_tree_viewer)

        self._export_csv_btn = QPushButton(self.tr("Export Matrix"))
        # Always blue; enabled/disabled not needed
        self._export_csv_btn.clicked.connect(self._export_csv)

        self._clear_btn = QPushButton(self.tr("Clear"))
        self._clear_btn.clicked.connect(self._clear_all)

        # Insert before Help button (rightmost in status_layout)
        # Order: [Run] [View Tree] [Export Matrix] [Clear] [Help]
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._run_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._view_tree_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._export_csv_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._clear_btn)

        # Consistent status-bar button widths across the app's tabs
        unify_status_button_sizes(self)

    def _connect_signals(self):
        self._file_edit.fileDropped.connect(self._on_file_dropped)
        self._file_edit.textChanged.connect(self._on_file_text_changed)

    # ── Slots ───────────────────────────────────────────────────────
    def _auto_suggest_output(self, path: str) -> None:
        """Auto-fill the output tree path from the input file, if empty."""
        if not self._out_edit.text().strip():
            base, _ = os.path.splitext(path)
            self._out_edit.setText(base + "_tree.nwk")

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
            self._auto_suggest_output(path)
            self._update_model_combo()

    def _on_file_text_changed(self, text: str):
        if text.strip() and os.path.isfile(text.strip()):
            self._update_model_combo()

    def _on_file_dropped(self, path: str):
        self._auto_suggest_output(path)
        self._update_model_combo()

    def _load_example(self):
        """Load the bundled csrA protein alignment example."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("phylo", "csrA_pro_mafft.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check the installation."),
            )
            return
        self._file_edit.setText(path)
        self._auto_suggest_output(path)
        self._update_model_combo()
        self.show_status(self.tr("Example loaded: csrA_pro_mafft.fasta"))

    def _update_model_combo(self):
        """Detect sequence type and update model choices accordingly."""
        path = self._file_edit.text().strip()
        if not path or not os.path.isfile(path):
            return
        try:
            seq_type = _detect_seq_type(path)
        except Exception:
            return
        current_data = self._model_combo.currentData()
        self._model_combo.clear()
        models = _DNA_MODELS if seq_type == "DNA" else _AA_MODELS
        for display, data in models:
            self._model_combo.addItem(self.tr(display), data)
        # Restore previous selection if still valid
        idx = self._model_combo.findData(current_data)
        self._model_combo.setCurrentIndex(idx if idx >= 0 else 0)
        tip = (
            self.tr(
                "p-distance: fraction of differing sites  |  JC69: Jukes-Cantor correction  |  "
                "K80: Kimura 2-parameter (transitions vs transversions)\n"
                "First time? NJ + p-distance is a safe start."
            )
            if seq_type == "DNA"
            else self.tr(
                "BLOSUM62: widely used for proteins  |  Dayhoff: PAM-based  |  identity: simple p-distance"
            )
        )
        self._model_combo.setToolTip(tip)
        self.log_message(
            self.tr(f"Detected sequence type: {'DNA' if seq_type == 'DNA' else 'Protein (AA)'}"),
            "INFO",
        )

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
            base, _ = os.path.splitext(input_path)
            output_path = base + "_tree.nwk"
            self._out_edit.setText(output_path)

        model = self._model_combo.currentData()
        method = self._method_combo.currentData()
        n_bootstrap = self._bootstrap_spin.value()

        self._set_running(True)
        if n_bootstrap > 0:
            self.log_message(
                self.tr(
                    f"Computing {method.upper()} tree ({model}) with {n_bootstrap} bootstrap replicates …"
                )
            )
        else:
            self.log_message(
                self.tr(f"Computing {method.upper()} tree ({model}) from {input_path} …")
            )
        self.show_status(self.tr("Computing distance matrix…"))

        self._thread = _DistanceTreeWorker(input_path, model, method, n_bootstrap)
        self._thread.finished_ok.connect(self._on_result)
        self._thread.finished_err.connect(self._on_error)
        self._thread.progress.connect(self._on_bootstrap_progress)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_bootstrap_progress(self, current: int, total: int):
        # Throttle: update status only every 10th replicate or at start/end
        if current % 10 == 0 or current == 1 or current == total:
            self.show_status(self.tr(f"Bootstrap replicate {current}/{total}…"))

    def _on_result(self, data: dict):
        self._matrix_data = data["matrix"]
        self._names = data["names"]
        self._newick_str = data["newick"]
        n_taxa = data["n_taxa"]
        n_bootstrap = data.get("n_bootstrap", 0)
        warning = data.get("warning", "")
        if warning:
            self.log_message(self.tr(warning), "WARNING")
            self.show_status(self.tr(warning))

        # Populate table
        self._populate_table(data["matrix"], data["names"])

        # Save tree to output file
        output_path = self._out_edit.text().strip()
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self._newick_str + "\n")
            self._last_treefile = output_path
            self._view_tree_btn.setVisible(True)
            boot_msg = f", {n_bootstrap} bootstrap replicates" if n_bootstrap else ""
            self.log_message(self.tr(f"Tree saved → {output_path}  ({n_taxa} taxa{boot_msg})"))
            status_msg = self.tr(
                f"{self._method_combo.currentText()} tree saved ({n_taxa} taxa{boot_msg})"
            )
            self.show_status(status_msg)
        except Exception as exc:
            self._last_treefile = ""
            self._view_tree_btn.setVisible(False)
            self.log_message(self.tr(f"Failed to save tree: {exc}"), "ERROR")
            self.show_status(self.tr("Tree computed but save failed"))

        self._set_running(False)
        self._thread = None

    def _on_error(self, msg: str):
        self.log_message(msg, "ERROR")
        self.show_status(self.tr(f"Error: {msg}"))
        self._set_running(False)
        self._thread = None

    def _open_tree_viewer(self):
        """Open the resulting tree file in the Toytree Visualization tab."""
        if not self._last_treefile or not os.path.isfile(self._last_treefile):
            return
        main_win = self.window()
        if main_win and hasattr(main_win, "open_toytree_visualization_tab"):
            main_win.open_toytree_visualization_tab()
            from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

            for i in range(main_win.tabs.count()):
                widget = main_win.tabs.widget(i)
                if isinstance(widget, ToytreeVisualizationTab):
                    widget._file_edit.setText(self._last_treefile)
                    main_win.tabs.setCurrentIndex(i)
                    break

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
                # Color-code off-diagonal only; the zero diagonal stays unstyled
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
                        row_vals = [
                            f"{v:.6f}" for v in self._matrix_data[i]
                        ]
                        f.write(name + "," + ",".join(row_vals) + "\n")
            self.log_message(self.tr(f"Matrix exported → {path}"))
            self.show_status(self.tr("Matrix exported"))
        except Exception as exc:
            self.log_message(self.tr(f"Export failed: {exc}"), "ERROR")

    def _clear_all(self):
        self._file_edit.clear()
        self._out_edit.clear()
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._matrix_data = None
        self._newick_str = ""
        self._names = []
        self._last_treefile = ""
        self._view_tree_btn.setVisible(False)
        self._bootstrap_spin.setValue(1000)
        # Reset model combo to DNA defaults
        self._model_combo.clear()
        for display, data in _DNA_MODELS:
            self._model_combo.addItem(self.tr(display), data)
        self._model_combo.setCurrentIndex(0)
        self.log_area.clear()
        self.show_status(self.tr("Cleared"))

    def _set_running(self, running: bool):
        self._run_btn.setEnabled(not running)
        self._file_edit.setEnabled(not running)
        self._model_combo.setEnabled(not running)
        self._method_combo.setEnabled(not running)
        self._bootstrap_spin.setEnabled(not running)
        self._out_edit.setEnabled(not running)
        self._browse_btn.setEnabled(not running)
        self._save_btn.setEnabled(not running)
        self._example_btn.setEnabled(not running)

    # ── Help ────────────────────────────────────────────────────────
    def show_help(self):
        help_text = """
<h2>Distance Tree Construction &mdash; NJ / UPGMA via BioPython</h2>

<p><b>What does this tool do?</b><br>
Computes a pairwise <b>distance matrix</b> from a multiple sequence alignment,
then builds a <b>Neighbor-Joining</b> or <b>UPGMA</b> phylogenetic tree.
Powered by <b>BioPython</b> — no external binaries needed.</p>

<h3>Quick Start</h3>
<ol>
<li>Load a FASTA (or PHYLIP, NEXUS, CLUSTAL) alignment file, or click <b>Example</b>
to load the bundled sample. Models auto-update based on DNA or Protein detection.</li>
<li>Choose a <b>distance model</b> and <b>tree method</b>.</li>
<li>Optionally set <b>Bootstrap</b> replicates for branch support.</li>
<li>Set the output <b>tree file (.nwk)</b> path (auto-suggested).</li>
<li>Click <b>Run</b> — the matrix appears below, tree saved to file.</li>
<li>Click <b>View Tree</b> to open the Newick tree in the <b>Tree Visualization</b> tab.</li>
<li>Use <b>Export Matrix</b> to save the distance table as CSV or Excel.</li>
</ol>

<h3>Distance Models</h3>
<ul>
<li><b>p-distance (identity)</b> &mdash; fraction of differing sites (DNA &amp; Protein).</li>
<li><b>Jukes-Cantor (JC69)</b> &mdash; DNA distance corrected for multiple substitutions (recommended for DNA).</li>
<li><b>Kimura 2-parameter (K80)</b> &mdash; DNA distance that separates transitions and transversions (recommended for DNA).</li>
<li><b>BLOSUM62</b> &mdash; widely used for protein alignments.</li>
<li><b>Dayhoff</b> &mdash; PAM-based substitution matrix (Protein).</li>
</ul>

<h3>Tree Methods</h3>
<ul>
<li><b>NJ</b> &mdash; Neighbor-Joining: fast, accurate, widely used.</li>
<li><b>UPGMA</b> &mdash; Unweighted Pair Group Method: assumes molecular clock (ultrametric).</li>
</ul>

<h3>Bootstrap</h3>
<p>Set <b>Bootstrap</b> &gt; 0 to compute branch support values via
column resampling. Bootstrap values appear as node labels in the output
Newick tree. Recommended: 100 for quick checks, 500–1000 for publication.</p>

<h3>Supported Input Formats</h3>
<ul>
<li><b>FASTA</b> &mdash; .fasta .fa .fas .fna .ffn .faa</li>
<li><b>PHYLIP</b> &mdash; .phy .phylip</li>
<li><b>NEXUS</b> &mdash; .nex .nxs</li>
<li><b>CLUSTAL</b> &mdash; .aln .clustal</li>
<li><b>Stockholm</b> &mdash; .sto</li>
</ul>

<h3>Output</h3>
<ul>
<li><b>Tree file</b> &mdash; Newick format (.nwk), ready for visualization in
Tree Visualization (Toytree) or IQ-TREE.</li>
<li><b>Distance Matrix</b> &mdash; displayed in the table; export to CSV or
Excel for heatmap plotting or external analysis.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Click <b>Example</b> to quickly load a bundled alignment and try the tool.</li>
<li>Files can be dragged &amp; dropped directly into the input field.</li>
<li>For large alignments (100+ taxa) the computation may take a few seconds.</li>
<li>NJ trees are unrooted by default; use <b>Tree Visualization</b> to re-root.</li>
<li>For maximum-likelihood trees, see <b>ML Tree Construction (IQ-TREE)</b>.</li>
</ul>
        """
        self.show_help_dialog("Help - Distance Tree Construction", help_text, 820, 580)
