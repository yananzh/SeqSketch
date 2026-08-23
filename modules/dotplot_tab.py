import os

import matplotlib
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit, unify_status_button_sizes
from utils.example_data import load_example_text, stage_example

matplotlib.use("QtAgg")
import re

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class DotPlotTab(BaseTabWidget):
    """Local DotPlot visualization tab (beginner-friendly)."""

    def __init__(self, parent=None):
        super().__init__("DotPlot", "sequence")

        self.run_btn.setText("Run")
        self._matrix = None
        self._seq_a_name = "Sequence A"
        self._seq_b_name = "Sequence B"

        # Accent Save Figure button right after Run
        self.export_plot_btn = QPushButton("Save Figure")
        self.export_plot_btn.setFixedWidth(110)
        self.export_plot_btn.setProperty("accentButton", True)
        self.export_plot_btn.setEnabled(False)
        self.export_plot_btn.clicked.connect(self.export_result)
        self.export_plot_btn.style().unpolish(self.export_plot_btn)
        self.export_plot_btn.style().polish(self.export_plot_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.run_btn) + 1, self.export_plot_btn
        )

        # Result Folder button (before Clear; enabled after export)
        self.open_folder_btn = QPushButton("Result Folder")
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.style().unpolish(self.open_folder_btn)
        self.open_folder_btn.style().polish(self.open_folder_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.clear_btn), self.open_folder_btn
        )
        self._last_export_dir = ""


        self.clear_btn.setFixedWidth(75)
        self.run_btn.setFixedWidth(75)
        self.help_btn.setFixedWidth(75)
        self._update_ui_layout()
        self._setup_parameters()
        self._setup_plot_canvas()
        unify_status_button_sizes(self)

    def _update_ui_layout(self):
        # File-only input: the text editor stays hidden as the content
        # store; a FileDropLineEdit shows the selected file path.
        self.input_text.hide()
        self.input_hint.hide()
        self.output_group.hide()

        ig = self.input_group.layout()
        ig.setContentsMargins(12, 10, 12, 2)
        ig.removeWidget(self.input_text)
        ig.removeWidget(self.upload_btn)

        self.input_group.setTitle("Input Sequence and Mode Selection")

        self.input_label.setText("Input FASTA file:")

        self.input_label.setFixedWidth(120)
        self.path_edit = FileDropLineEdit()
        self.path_edit.setPlaceholderText("Select or drop a FASTA file (one or two sequences)...")
        self.path_edit.file_dropped.connect(self._load_file_path)

        # One row: label + path field + Example + Browse
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input_label)
        row.addWidget(self.path_edit, 1)

        self.example_btn = QPushButton("Example")
        self.example_btn.setToolTip("Load example sequences for DotPlot")
        self.example_btn.clicked.connect(self._load_example)
        row.addWidget(self.example_btn)

        self.upload_btn.setText("Browse")
        self.upload_btn.setFixedWidth(90)
        row.addWidget(self.upload_btn)

        ig.insertLayout(1, row)

    def _load_file_path(self, file_path):
        """Read the file into the hidden content store and show its path."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, "File Read Error", str(e))
            return
        self.input_text.setPlainText(content)
        self.input_hint.clear()
        self.path_edit.setText(file_path)
        self.show_status(f"Loaded file: {os.path.basename(file_path)}")

    def _setup_parameters(self):
        row = QHBoxLayout()
        row.setSpacing(8)  # match the file row's spacing for aligned controls

        # Fixed-width label so the controls align with the file row above
        mode_lbl = QLabel("Compare Mode:")
        mode_lbl.setFixedWidth(120)
        row.addWidget(mode_lbl)
        self.mode_box = QComboBox()
        self.mode_box.addItems([
            "Auto (2 FASTA records -> pairwise; 1 record -> self)",
            "Force self-comparison (use first sequence)",
            "Force pairwise (use first two sequences)",
        ])
        self.mode_box.setMinimumWidth(350)
        row.addWidget(self.mode_box)

        row.addWidget(QLabel("Word Size (k-mer):"))
        self.word_size_box = QSpinBox()
        self.word_size_box.setRange(1, 20)
        self.word_size_box.setValue(1)
        self.word_size_box.setFixedWidth(80)
        self.word_size_box.setToolTip(
            "Exact k-mer window size.\n"
            "DNA: 1-5 recommended\n"
            "Protein: 1-2 recommended\n"
            "1 = most sensitive; larger values reduce noise."
        )
        row.addWidget(self.word_size_box)

        row.addStretch()
        # Parameters live inside the input group, below the file row
        self.input_group.layout().addLayout(row)

    def _setup_plot_canvas(self):
        """Add a scrollable matplotlib canvas (same form as Sequence Logo)."""
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setMinimumHeight(240)
        # Center the figure when the viewport is larger than the canvas
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Inner wrapper widget isolates canvas sizing from scroll-area layout
        self._canvas_inner = QWidget()
        self._canvas_vbox = QVBoxLayout(self._canvas_inner)
        self._canvas_vbox.setContentsMargins(0, 0, 0, 0)
        self._canvas_vbox.setSpacing(0)
        self._scroll_area.setWidget(self._canvas_inner)

        # Near-square figure: dotplots are square-ish (len_a x len_b matrix)
        self.figure = Figure(figsize=(6, 6), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(220)

        self._canvas_vbox.addWidget(self.canvas)

        # Set initial inner widget size to match the figure so the
        # placeholder is visible from the start.
        dpi = self.figure.dpi
        self._canvas_inner.setFixedSize(
            int(self.figure.get_figwidth() * dpi),
            int(self.figure.get_figheight() * dpi),
        )

        self.add_content_widget(self._scroll_area)
        self._draw_placeholder_plot()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sequence file",
            "",
            "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;All Files (*)",
        )
        if file_path:
            self._load_file_path(file_path)

    def _load_example(self):
        staged = stage_example("protein", "pairwise_pro.fasta")
        if not staged:
            QMessageBox.information(self, "Example", "Example data not found.")
            return
        try:
            with open(staged, "r", encoding="utf-8") as f:
                self.input_text.setPlainText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "File Read Error", str(e))
            return
        self.path_edit.setText(staged)
        self.show_status("Example loaded")

    def _parse_fasta_records(self, text: str):
        records = []
        header = None
        seq_lines = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    records.append((header, "".join(seq_lines)))
                header = line[1:].strip() or f"seq{len(records) + 1}"
                seq_lines = []
            else:
                seq_lines.append(line)
        if header is not None:
            records.append((header, "".join(seq_lines)))
        return records

    def _sanitize_seq(self, seq: str):
        seq = seq.upper().replace("U", "T")
        seq = re.sub(r"\s+", "", seq)
        seq = re.sub(r"[^A-Z]", "", seq)
        return seq

    def _build_dot_matrix(self, seq_a: str, seq_b: str, k: int):
        """
        Build binary dotplot matrix using exact k-mer hits.
        For each exact k-mer hit at (i, j), mark a short diagonal of length k.
        """
        len_a, len_b = len(seq_a), len(seq_b)
        matrix = np.zeros((len_a, len_b), dtype=np.uint8)

        if len_a < k or len_b < k:
            return matrix

        index_b = {}
        for j in range(len_b - k + 1):
            kmer = seq_b[j : j + k]
            index_b.setdefault(kmer, []).append(j)

        for i in range(len_a - k + 1):
            kmer = seq_a[i : i + k]
            hits = index_b.get(kmer)
            if not hits:
                continue
            for j in hits:
                dmax = min(k, len_a - i, len_b - j)
                if dmax > 0:
                    matrix[i : i + dmax, j : j + dmax] |= np.eye(dmax, dtype=np.uint8)

        return matrix

    def _draw_placeholder_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "DotPlot will appear here after clicking 'Generate DotPlot'",
            ha="center",
            va="center",
            fontsize=11,
            color="#888",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    def _draw_dotplot(self, matrix, name_a, name_b, k):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        ax.imshow(
            matrix,
            cmap="Greys",
            interpolation="nearest",
            origin="upper",
            aspect="auto",
        )
        ax.set_title(f"DotPlot (k-mer = {k})", fontsize=11)
        ax.set_xlabel(f"{name_b} position")
        ax.set_ylabel(f"{name_a} position")
        ax.grid(False)
        self.canvas.draw()

    def run(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please input one or two sequences.")
            return

        # Parse FASTA. If not FASTA, treat as a single raw sequence.
        if ">" in text:
            records = self._parse_fasta_records(text)
        else:
            records = [("sequence_1", text)]

        records = [(h, self._sanitize_seq(s)) for h, s in records if self._sanitize_seq(s)]
        if not records:
            QMessageBox.warning(self, "Input Error", "No valid sequence found.")
            return

        mode = self.mode_box.currentIndex()
        if mode == 1:  # force self
            seq_a_name, seq_a = records[0]
            seq_b_name, seq_b = records[0], records[0][1]
            seq_b_name = seq_a_name + " (self)"
        elif mode == 2:  # force pairwise
            if len(records) < 2:
                QMessageBox.warning(
                    self,
                    "Input Error",
                    "Force pairwise mode requires at least two FASTA records.",
                )
                return
            seq_a_name, seq_a = records[0]
            seq_b_name, seq_b = records[1]
        else:  # auto
            if len(records) >= 2:
                seq_a_name, seq_a = records[0]
                seq_b_name, seq_b = records[1]
            else:
                seq_a_name, seq_a = records[0]
                seq_b_name, seq_b = records[0], records[0][1]
                seq_b_name = seq_a_name + " (self)"

        k = self.word_size_box.value()
        if len(seq_a) < k or len(seq_b) < k:
            QMessageBox.warning(
                self,
                "Input Error",
                f"Word size k={k} is too large for input length ({len(seq_a)} / {len(seq_b)}).",
            )
            return

        # safety warning for very large matrices
        if len(seq_a) * len(seq_b) > 30_000_000:
            ans = QMessageBox.question(
                self,
                "Large Matrix Warning",
                "The dotplot matrix is large and may be slow to render. Continue?",
            )
            if ans != QMessageBox.StandardButton.Yes:
                self.status_label.setText("Cancelled by user.")
                return

        matrix = self._build_dot_matrix(seq_a, seq_b, k)
        self._matrix = matrix
        self._seq_a_name = seq_a_name
        self._seq_b_name = seq_b_name
        self._draw_dotplot(matrix, seq_a_name, seq_b_name, k)
        self.export_plot_btn.setEnabled(True)

        dot_count = int(matrix.sum())
        density = (dot_count / matrix.size) * 100 if matrix.size else 0.0
        self.status_label.setText(f"Generated: {dot_count} dots, density {density:.4f}%")

    def clear(self):
        super().clear()
        self._matrix = None
        self.path_edit.clear()
        self.export_plot_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(False)
        self._draw_placeholder_plot()

    def _open_output_folder(self):
        """Open the folder of the most recently exported figure."""
        if self._last_export_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

    def export_result(self):
        if self._matrix is None:
            QMessageBox.warning(self, "No Figure", "Please generate a DotPlot first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save DotPlot Figure",
            "dotplot.png",
            "PNG files (*.png);;SVG files (*.svg);;PDF files (*.pdf);;All Files (*)",
        )
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches="tight")
                self.status_label.setText(f"Exported: {os.path.basename(file_path)}")
                self._last_export_dir = os.path.dirname(file_path)
                self.open_folder_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def show_help(self):
        help_text = """
<h2>DotPlot &mdash; Sequence Similarity Dot Matrix</h2>
<p><b>What does this tool do?</b><br>
DotPlot visualizes sequence similarity as a 2D map. Matching regions appear as diagonal patterns, making it easy to spot repeats, inversions, and conserved domains.</p>

<h3>Quick Start</h3>
<ol>
<li>Load a FASTA file with <b>Browse</b> or drag &amp; drop it
onto the input area. One sequence gives a self-comparison; two
sequences give a pairwise comparison.</li>
<li>Choose word size (k-mer). Start with <b>k=1</b> for sensitive, <b>k=2</b> for cleaner plots.</li>
<li>Click <b>Run</b>.</li>
<li>Use <b>Save Figure</b> to export the plot as PNG, PDF, or SVG, then
<b>Result Folder</b> to locate the saved file.</li>
</ol>

<h3>Comparison Modes</h3>
<ul>
<li><b>Auto</b> — 2 FASTA records produce pairwise; 1 record produces self-comparison.</li>
<li><b>Force self-comparison</b> — use only the first sequence against itself.</li>
<li><b>Force pairwise</b> — use the first two sequences.</li>
</ul>

<h3>Word Size (k-mer)</h3>
<p>A hit is recorded wherever two sequences share an exact k-mer match. Lower values give more dots (higher sensitivity); higher values give fewer dots (less noise).</p>

<h3>How to Interpret</h3>
<ul>
<li>Main diagonal — overall similarity in the same orientation.</li>
<li>Parallel diagonals — repeated regions.</li>
<li>Anti-diagonal patterns — possible inversions or reverse similarity.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>If plot is too dense, increase word size from 1 to 2 or 3.</li>
<li>If plot is too sparse, decrease word size.</li>
<li>For long sequences, compare subsequences first for faster rendering.</li>
</ul>
        """
        from PyQt6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("Help - DotPlot")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml(help_text)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()
