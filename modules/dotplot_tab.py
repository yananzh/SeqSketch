from utils.common_components import BaseTabWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt

import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import numpy as np
import re


class DotPlotTab(BaseTabWidget):
    """Local DotPlot visualization tab (beginner-friendly)."""

    def __init__(self, parent=None):
        super().__init__("DotPlot", "sequence")

        self.run_btn.setText("Generate DotPlot")
        self._matrix = None
        self._seq_a_name = "Sequence A"
        self._seq_b_name = "Sequence B"

        self._update_ui_layout()
        self._setup_parameters()
        self._setup_plot_canvas()
        self._setup_drag_drop()

    def _update_ui_layout(self):
        self.input_text.setPlaceholderText(
            "Paste one or two sequences in FASTA format (recommended), or drag-and-drop a FASTA file...\n\n"
            "Example (two sequences):\n"
            ">seqA\n"
            "ATGCTAGCTAGCTAGCTAGC\n"
            ">seqB\n"
            "ATGCGAGCTTGCTAGATAGC\n\n"
            "If only one sequence is provided, DotPlot performs self-comparison."
        )
        self.input_text.setMinimumHeight(170)
        self.input_hint.hide()
        self.output_label.hide()
        self.output_text.hide()
        self.export_btn.hide()
        self.copy_btn.hide()

    def _setup_parameters(self):
        # Comparison mode
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Comparison Mode:")
        self.mode_box = QComboBox()
        self.mode_box.addItems([
            "Auto (2 FASTA records -> pairwise; 1 record -> self)",
            "Force self-comparison (use first sequence)",
            "Force pairwise (use first two sequences)",
        ])
        self.mode_box.setMinimumWidth(350)
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self.mode_box)
        mode_row.addStretch()

        # Word size
        word_row = QHBoxLayout()
        word_lbl = QLabel("Word Size (k-mer):")
        self.word_size_box = QSpinBox()
        self.word_size_box.setRange(1, 20)
        self.word_size_box.setValue(1)
        self.word_size_box.setMinimumWidth(90)
        word_hint = QLabel("(1 = most sensitive; larger values reduce noise)")
        word_hint.setStyleSheet("color: #777;")
        word_row.addWidget(word_lbl)
        word_row.addWidget(self.word_size_box)
        word_row.addWidget(word_hint)
        word_row.addStretch()

        self.add_content_layout(mode_row)
        self.add_content_layout(word_row)

    def _setup_plot_canvas(self):
        self.figure = Figure(figsize=(7.5, 4.5), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.canvas.setMinimumHeight(300)
        self.add_content_widget(self.toolbar)
        self.add_content_widget(self.canvas)
        self._draw_placeholder_plot()

    def _setup_drag_drop(self):
        self.input_text.setAcceptDrops(True)
        self.input_text.dragEnterEvent = self._drag_enter_event
        self.input_text.dropEvent = self._drop_event

    def _drag_enter_event(self, event):
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.clear()
                event.acceptProposedAction()
            except Exception as e:
                self.status_label.setText(f"Error loading file: {e}")
                event.ignore()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sequence file",
            "",
            "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.clear()
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

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
                    matrix[i : i + dmax, j : j + dmax] = np.eye(dmax, dtype=np.uint8)

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
            self.status_label.setText("Please input one or two sequences.")
            return

        # Parse FASTA. If not FASTA, treat as a single raw sequence.
        if ">" in text:
            records = self._parse_fasta_records(text)
        else:
            records = [("sequence_1", text)]

        records = [
            (h, self._sanitize_seq(s)) for h, s in records if self._sanitize_seq(s)
        ]
        if not records:
            self.status_label.setText("No valid sequence found.")
            return

        mode = self.mode_box.currentIndex()
        if mode == 1:  # force self
            seq_a_name, seq_a = records[0]
            seq_b_name, seq_b = records[0], records[0][1]
            seq_b_name = seq_a_name + " (self)"
        elif mode == 2:  # force pairwise
            if len(records) < 2:
                self.status_label.setText(
                    "Force pairwise mode requires at least two FASTA records."
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
            self.status_label.setText(
                f"Word size k={k} is too large for input length ({len(seq_a)} / {len(seq_b)})."
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

        dot_count = int(matrix.sum())
        density = (dot_count / matrix.size) * 100 if matrix.size else 0.0
        self.status_label.setText(
            f"DotPlot generated: {dot_count} dots, density {density:.4f}%."
        )

    def clear(self):
        super().clear()
        self._matrix = None
        self._draw_placeholder_plot()

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
                self.status_label.setText(f"Figure exported: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def show_help(self):
        help_text = """
<h3>DotPlot (Local)</h3>
<p><b>Description:</b></p>
<p>DotPlot visualizes sequence similarity as a 2D map. Matching regions appear as diagonal patterns.</p>

<p><b>Quick Start:</b></p>
<ol>
<li>Paste one sequence (self-comparison) or two sequences (pairwise) in FASTA format.</li>
<li>Choose word size (k-mer). Start with <b>k=1</b> or <b>k=2</b>.</li>
<li>Click <b>Generate DotPlot</b>.</li>
<li>Use the toolbar to zoom, pan, or export the image if needed.</li>
</ol>

<p><b>Parameters:</b></p>
<ul>
<li><b>Comparison Mode:</b> Auto / force self / force pairwise.</li>
<li><b>Word Size:</b> Exact k-mer match length. Larger values reduce noise.</li>
</ul>

<p><b>How to interpret:</b></p>
<ul>
<li>Main diagonal: overall similarity in the same direction.</li>
<li>Parallel diagonals: repeated regions.</li>
<li>Anti-diagonal-like patterns: possible inversions/reverse similarity.</li>
</ul>

<p><b>Tips for beginners:</b></p>
<ul>
<li>If plot is too dense, increase word size from 1 to 2/3.</li>
<li>If plot is too sparse, decrease word size.</li>
<li>For long sequences, compare subsequences first for faster rendering.</li>
</ul>
        """
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - DotPlot")
        dialog.setFixedSize(850, 600)
        layout = QVBoxLayout()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)

        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        dialog.exec()
