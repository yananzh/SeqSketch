"""Hydrophobicity Plot Tab — sliding-window hydrophobicity analysis for protein sequences."""

import os

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, unify_status_button_sizes
from utils.example_data import load_example_text

# ── Hydrophobicity scales ───────────────────────────────────────────────────
# Values for the 20 standard amino acids (A R N D C Q E G H I L K M F P S T W Y V)

SCALES = {
    "Kyte-Doolittle": {
        "A": 1.8,
        "R": -4.5,
        "N": -3.5,
        "D": -3.5,
        "C": 2.5,
        "Q": -3.5,
        "E": -3.5,
        "G": -0.4,
        "H": -3.2,
        "I": 4.5,
        "L": 3.8,
        "K": -3.9,
        "M": 1.9,
        "F": 2.8,
        "P": -1.6,
        "S": -0.8,
        "T": -0.7,
        "W": -0.9,
        "Y": -1.3,
        "V": 4.2,
    },
    "Hopp-Woods": {
        "A": -0.5,
        "R": 3.0,
        "N": 0.2,
        "D": 3.0,
        "C": -1.0,
        "Q": 0.2,
        "E": 3.0,
        "G": 0.0,
        "H": -0.5,
        "I": -1.8,
        "L": -1.8,
        "K": 3.0,
        "M": -1.3,
        "F": -2.5,
        "P": 0.0,
        "S": 0.3,
        "T": -0.4,
        "W": -3.4,
        "Y": -2.3,
        "V": -1.5,
    },
    "Eisenberg": {
        "A": 0.62,
        "R": -2.53,
        "N": -0.78,
        "D": -0.90,
        "C": 0.29,
        "Q": -0.85,
        "E": -0.74,
        "G": 0.48,
        "H": -0.40,
        "I": 1.38,
        "L": 1.06,
        "K": -1.50,
        "M": 0.64,
        "F": 1.19,
        "P": 0.12,
        "S": -0.18,
        "T": -0.05,
        "W": 0.81,
        "Y": 0.26,
        "V": 1.08,
    },
    "Engelman (GES)": {
        "A": 1.6,
        "R": -12.3,
        "N": -4.8,
        "D": -9.2,
        "C": 2.0,
        "Q": -4.1,
        "E": -8.2,
        "G": 1.0,
        "H": -3.0,
        "I": 3.1,
        "L": 2.8,
        "K": -8.8,
        "M": 3.4,
        "F": 3.7,
        "P": -0.2,
        "S": 0.6,
        "T": 1.2,
        "W": 1.9,
        "Y": -0.7,
        "V": 2.6,
    },
}


class HydrophobicityPlotTab(BaseTabWidget):
    """Hydrophobicity Plot — sliding-window Kyte-Doolittle style analysis."""

    def __init__(self, parent=None):
        super().__init__("Hydrophobicity Plot", "sequence")

        self.run_btn.setText("Plot")
        self.run_btn.setFixedWidth(100)
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()
        if hasattr(self, "export_btn"):
            self.export_btn.hide()
        self.output_group.hide()
        self.output_text.hide()
        self.output_label.hide()
        self.input_hint.hide()

        self.input_text.setPlaceholderText(
            "Paste a protein sequence in FASTA format or drag-and-drop a file...\n\n"
            "Example:\n>my_protein\nMKLFVTGASRGIGRAIALRLAKDGA"
        )
        self.input_text.setMaximumHeight(100)

        self._setup_parameters()
        self._add_plot_canvas()
        self._setup_drag_drop()
        self.current_figure = None

        # Place Example button horizontally with upload_btn
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ig_layout = self.input_group.layout()
        ig_layout.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.upload_btn, 1)
        btn_row.addWidget(self.example_btn, 1)
        ig_layout.insertLayout(1, btn_row)

        # Export Plot button between Plot and Clear in the status row.
        self.export_plot_btn = QPushButton(self.tr("Export Plot"))
        self.export_plot_btn.setFixedWidth(110)
        self.export_plot_btn.setProperty("accentButton", True)
        self.export_plot_btn.setEnabled(False)
        self.export_plot_btn.clicked.connect(self.export_result)
        self.export_plot_btn.style().unpolish(self.export_plot_btn)
        self.export_plot_btn.style().polish(self.export_plot_btn)
        _idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(_idx + 1, self.export_plot_btn)
        # Add Result Folder button after Export Plot
        self.open_folder_btn = QPushButton(self.tr("Result Folder"))
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.style().unpolish(self.open_folder_btn)
        self.open_folder_btn.style().polish(self.open_folder_btn)
        self.status_layout.insertWidget(_idx + 2, self.open_folder_btn)
        self._last_export_dir = ""
        unify_status_button_sizes(self)

    def _load_example(self):
        """Load the bundled protein example (only the first record is shown)."""
        text = load_example_text("protein", "protein_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        try:
            records = self.parse_fasta(text)
        except Exception:
            records = []
        if records:
            header, seq = records[0]
            text = f">{header}\n{seq}\n"
        self.input_text.setPlainText(text)
        self.show_status(self.tr("Loaded example data: protein_example.fasta"))

    # ── Layout ──────────────────────────────────────────────────────────────

    def _setup_parameters(self):
        param_group = QGroupBox("Plot Options")
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 12, 0, 12)
        pg_layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(16)

        # Scale selector
        row.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(list(SCALES.keys()))
        self.scale_combo.setCurrentText("Kyte-Doolittle")
        self.scale_combo.setMinimumWidth(180)
        self.scale_combo.setToolTip(
            "Kyte-Doolittle: classic hydropathy (positive = hydrophobic)\n"
            "Hopp-Woods: antigenicity / hydrophilicity (positive = hydrophilic)\n"
            "Eisenberg: consensus hydrophobicity\n"
            "Engelman (GES): transmembrane helix prediction"
        )
        row.addWidget(self.scale_combo)

        # Window size
        row.addWidget(QLabel("Window:"))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(3, 31)
        self.window_spin.setSingleStep(2)
        self.window_spin.setValue(9)
        self.window_spin.setSuffix(" aa")
        self.window_spin.setToolTip(
            "Sliding window size (odd values 3–31). Larger windows smooth the curve."
        )
        row.addWidget(self.window_spin)

        row.addStretch()
        pg_layout.addLayout(row)
        self.content_area.insertWidget(1, param_group)

    def _add_plot_canvas(self):
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setMinimumHeight(210)

        self.figure = Figure(figsize=(10, 3.5))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(250)
        self._scroll_area.setWidget(self.canvas)

        plot_label = QLabel("Hydrophobicity Profile:")
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(plot_label)
        plot_layout.addWidget(self._scroll_area)
        self.content_area.insertLayout(self.content_area.count() - 1, plot_layout)
        self._draw_placeholder_plot()

    def _draw_placeholder_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "Hydrophobicity plot will appear here after clicking 'Plot'",
            ha="center",
            va="center",
            fontsize=12,
            color="#999",
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    # ── Core logic ──────────────────────────────────────────────────────────

    def run(self):
        self.status_label.setText("")
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please input a protein sequence.")
            return

        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "Format Error", str(e))
            return
        if not records:
            QMessageBox.warning(self, "Input Error", "No valid FASTA sequences detected.")
            return

        # Only the first sequence is analysed.
        header, seq = records[0]
        seq = "".join(c for c in seq.upper() if c.isalpha())
        if not seq:
            QMessageBox.warning(self, "Input Error", "Sequence is empty after cleaning.")
            return

        scale_name = self.scale_combo.currentText()
        scale = SCALES[scale_name]
        window = self.window_spin.value()

        # Convert sequence to scores
        try:
            scores = np.array([scale[aa] for aa in seq], dtype=float)
        except KeyError as e:
            QMessageBox.warning(
                self,
                "Sequence Error",
                f"Unknown amino acid '{e.args[0]}' at position. "
                f"Ensure the sequence uses standard one-letter codes.",
            )
            return

        averaged = self._window_average(scores, window)
        self._draw_plot(seq, averaged, scale_name, window, header)
        self.export_plot_btn.setEnabled(True)
        self.status_label.setText(f"Plotted {scale_name} (window={window}) — {len(seq)} residues")

    @staticmethod
    def _window_average(scores: np.ndarray, window: int) -> np.ndarray:
        """Sliding-window mean; positions with < half a window are NaN."""
        half = window // 2
        averaged = np.full_like(scores, np.nan)
        for i in range(len(scores)):
            start = max(0, i - half)
            end = min(len(scores), i + half + 1)
            if end - start >= window // 2 + 1:  # at least half the window
                averaged[i] = np.mean(scores[start:end])
        return averaged

    def _draw_plot(self, seq, scores, scale_name: str, window: int, header: str):
        """Draw the single-sequence hydrophobicity profile."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        x = np.arange(1, len(seq) + 1)

        # Fill above/below zero differently
        ax.fill_between(
            x, 0, scores, where=(scores > 0), color="#d9534f", alpha=0.35, label="Hydrophobic"
        )
        ax.fill_between(
            x, 0, scores, where=(scores < 0), color="#5bc0de", alpha=0.35, label="Hydrophilic"
        )
        ax.plot(x, scores, color="#333", linewidth=1.2)
        ax.axhline(y=0, color="#999", linestyle="--", linewidth=0.8)

        ax.set_xlabel("Residue Position", fontsize=12)
        ax.set_ylabel(f"{scale_name} Score", fontsize=12)
        ax.set_title(
            f"Hydrophobicity Plot — {scale_name} (window={window})\n{header}",
            fontsize=13,
            fontweight="bold",
        )
        ax.set_xlim(1, len(seq))
        ax.legend(loc="upper right", fontsize=9)

        self.figure.tight_layout()
        self.current_figure = self.figure
        self.canvas.draw()

    def clear(self):
        self.input_text.clear()
        self._draw_placeholder_plot()
        self.current_figure = None
        self.export_plot_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(False)
        self.status_label.setText("Cleared")

    def _open_output_folder(self):
        """Open the folder of the most recently exported figure."""
        if self._last_export_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

    def export_result(self):
        if self.current_figure is None:
            QMessageBox.warning(self, "Export Error", "Generate a plot first.")
            return
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Hydrophobicity Plot",
            "hydrophobicity_plot.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)",
        )
        if file_path:
            try:
                self.current_figure.savefig(file_path, dpi=300, bbox_inches="tight")
                self.status_label.setText(f"Figure saved: {file_path}")
                self._last_export_dir = os.path.dirname(file_path)
                self.open_folder_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Failed to save figure:\n{str(e)}")

    def show_help(self):
        from PyQt6.QtWidgets import (
            QDialog,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
        )

        help_text = """
<h2>Hydrophobicity Plot &mdash; Sliding-Window Analysis</h2>

<p><b>What does this tool do?</b><br>
It computes a hydrophobicity score for each residue position using a sliding
window, then plots the profile along the protein sequence. Positive scores
indicate hydrophobic regions; negative scores indicate hydrophilic regions.</p>

<h3>Scales</h3>
<ul>
<li><b>Kyte-Doolittle</b> &mdash; the classic hydropathy scale. Values > 0
are hydrophobic. Widely used to identify transmembrane helices and
signal peptides.</li>
<li><b>Hopp-Woods</b> &mdash; hydrophilicity / antigenicity scale.
Positive values indicate regions likely to be antigenic epitopes.</li>
<li><b>Eisenberg</b> &mdash; consensus normalized hydrophobicity.
Balanced across multiple experimental datasets.</li>
<li><b>Engelman (GES)</b> &mdash; optimised for transmembrane helix
prediction. Uses the Goldman-Engelman-Steitz scale.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Use <b>window = 19&ndash;21</b> for transmembrane helix hunting with
the Kyte-Doolittle or Engelman scale.</li>
<li>Use <b>window = 7&ndash;9</b> for general hydropathy profiling.</li>
<li>Stretches where the score stays above ~1.6 (Kyte-Doolittle) for
20+ residues suggest a transmembrane helix.</li>
<li>Only the first FASTA record is analysed &mdash; multi-record files
should be split before use</li>
<li>Click <b>Export Plot</b> to save the figure as PNG / PDF / SVG</li>
</ul>
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Hydrophobicity Plot")
        dialog.resize(560, 420)
        dialog.setMinimumSize(400, 300)
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMargin(20)
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        dialog.setLayout(layout)
        dialog.exec()

    # ── Drag & drop + FASTA parsing ─────────────────────────────────────────

    def _setup_drag_drop(self):
        self.input_text.setAcceptDrops(True)

        def drag_enter(e):
            md = e.mimeData()
            if md.hasUrls():
                urls = md.urls()
                if urls and urls[0].toLocalFile():
                    e.acceptProposedAction()
                    return
            e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.input_text.setPlainText(content)
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))

        self.input_text.dragEnterEvent = drag_enter
        self.input_text.dropEvent = drop

    def parse_fasta(self, text):
        records = []
        lines = text.strip().split("\n")
        current_header = None
        current_seq = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_header is not None:
                    seq = "".join(current_seq)
                    if seq:
                        records.append((current_header, seq))
                current_header = line[1:].strip()
                current_seq = []
            else:
                current_seq.append(line)
        if current_header is not None:
            seq = "".join(current_seq)
            if seq:
                records.append((current_header, seq))
        return records
