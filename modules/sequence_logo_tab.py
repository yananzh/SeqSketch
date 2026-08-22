import os

import matplotlib
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit, unify_status_button_sizes
from utils.example_data import stage_example

matplotlib.use("QtAgg")
import logomaker
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class SequenceLogoTab(BaseTabWidget):
    """Sequence Logo Tab - Generate sequence logos for DNA or protein sequences"""

    def __init__(self, parent=None):
        super().__init__("Sequence Logo (Logomaker)", "sequence")

        # Customize base widgets
        self.run_btn.setText("Run")
        self.export_btn.setText("Save Figure")
        self.export_btn.setFixedWidth(110)
        self.export_btn.setProperty("accentButton", True)
        self.export_btn.style().unpolish(self.export_btn)
        self.export_btn.style().polish(self.export_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.run_btn) + 1, self.export_btn
        )
        self.help_btn.setFixedWidth(75)
        self.run_btn.setFixedWidth(75)
        self.clear_btn.setFixedWidth(75)

        # Result Folder button (before Clear; enabled after export)
        self.open_folder_btn = QPushButton(self.tr("Result Folder"))
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

        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()

        # File-only input: the text editor stays hidden as the content
        # store; a FileDropLineEdit shows the selected file path.
        self.input_text.hide()
        self.input_hint.hide()
        self.output_group.hide()
        self.output_text.hide()
        self.output_label.hide()

        ig = self.input_group.layout()
        ig.setContentsMargins(12, 10, 12, 2)
        ig.removeWidget(self.input_text)
        ig.removeWidget(self.upload_btn)

        self.input_label.setText("Input FASTA file:")
        self.input_label.setFixedWidth(120)

        self.path_edit = FileDropLineEdit()
        self.path_edit.setPlaceholderText(
            "Select or drop an aligned FASTA file (sequences must be equal length)..."
        )
        self.path_edit.file_dropped.connect(self._load_file_path)

        # One row: label + path field + Example + Browse
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input_label)
        row.addWidget(self.path_edit, 1)

        self.example_btn = QPushButton("Example")
        self.example_btn.setFixedWidth(90)
        self.example_btn.setToolTip(self.tr("Load example sequences for Sequence Logo"))
        self.example_btn.clicked.connect(self._load_example)
        row.addWidget(self.example_btn)

        self.upload_btn.setText("Browse")
        self.upload_btn.setFixedWidth(90)
        row.addWidget(self.upload_btn)

        ig.insertLayout(1, row)

        # ── Parameter group ───────────────────────────────────────────
        self._setup_parameters()

        # ── Matplotlib canvas ─────────────────────────────────────────
        self._add_plot_canvas()

        # Store current figure for export
        self.current_figure = None
        unify_status_button_sizes(self)

    def _clear_loaded_hint(self):
        self.input_hint.clear()
        self.input_hint.hide()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sequence file",
            "",
            "FASTA/TXT (*.fasta *.fa *.txt);;All Files (*)",
        )
        if file_path:
            self._load_file_path(file_path)

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

    def _load_example(self):
        staged = stage_example("dna", "seqlog_dna_example.fasta")
        if not staged:
            QMessageBox.information(self, self.tr("Example"), self.tr("Example data not found."))
            return
        try:
            with open(staged, "r", encoding="utf-8") as f:
                self.input_text.setPlainText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "File Read Error", str(e))
            return
        self.input_hint.clear()
        self.path_edit.setText(staged)
        self.show_status(self.tr("Example loaded"))

    # ── Layout helpers ──────────────────────────────────────────────────────

    def _setup_parameters(self):
        """Create a grouped parameter section with both controls in one row."""
        param_group = QGroupBox("Logo Options")
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 12, 0, 12)
        pg_layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(16)

        # Sequence Type
        type_label = QLabel("Sequence Type:")
        self.seq_type_combo = QComboBox()
        self.seq_type_combo.addItems(["Auto Detect", "DNA", "Protein"])
        self.seq_type_combo.setCurrentIndex(0)
        self.seq_type_combo.setMinimumWidth(140)
        row.addWidget(type_label)
        row.addWidget(self.seq_type_combo)

        # Display Mode
        mode_label = QLabel("Display Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Probability", "Information"])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setMinimumWidth(140)
        self.mode_combo.setToolTip(
            "Probability: Shows frequency of each base/residue at each position\n"
            "Information: Shows information content (bits) based on sequence conservation"
        )
        row.addWidget(mode_label)
        row.addWidget(self.mode_combo)

        # Inline hint for the currently selected mode
        self._mode_hint = QLabel("Height = letter frequency (0–1)")
        self._mode_hint.setStyleSheet("color: #777; font-size: 12px;")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        row.addWidget(self._mode_hint)
        row.addStretch()

        pg_layout.addLayout(row)
        self.content_area.insertWidget(1, param_group)

    def _on_mode_changed(self, text):
        hints = {
            "Probability": "Height = letter frequency (0–1)",
            "Information": "Height = conservation in bits (DNA max 2, protein max ~4.32)",
        }
        self._mode_hint.setText(hints.get(text, ""))

    def _add_plot_canvas(self):
        """Add a horizontally scrollable matplotlib canvas for long sequences."""
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setMinimumHeight(240)
        self._scroll_max_w = None

        # Inner wrapper widget isolates canvas sizing from scroll-area layout
        self._canvas_inner = QWidget()
        self._canvas_vbox = QVBoxLayout(self._canvas_inner)
        self._canvas_vbox.setContentsMargins(0, 0, 0, 0)
        self._canvas_vbox.setSpacing(0)
        self._scroll_area.setWidget(self._canvas_inner)

        self.figure = Figure(figsize=(10, 3))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(200)

        self._canvas_vbox.addWidget(self.canvas)

        # Set initial inner widget size to match figure so the placeholder
        # is visible from the start.
        dpi = self.figure.dpi
        self._canvas_inner.setFixedSize(
            int(self.figure.get_figwidth() * dpi),
            int(self.figure.get_figheight() * dpi),
        )

        self.content_area.insertWidget(max(0, self.content_area.count() - 1), self._scroll_area)

        self._draw_placeholder_plot()

    def _draw_placeholder_plot(self):
        """Draw a simple placeholder on the canvas."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "Sequence Logo will appear here after generation",
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

    def run(self):
        """Generate sequence logo"""
        self.status_label.setText("")
        text = self.input_text.toPlainText().strip()

        if not text:
            QMessageBox.warning(self, "Input Error", "Please input or load FASTA sequences.")
            return

        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "Format Error", str(e))
            return

        if not records:
            QMessageBox.warning(self, "Input Error", "No valid FASTA sequences detected.")
            return

        # Extract sequences
        sequences = [seq.upper() for _, seq in records]

        # Check if sequences are aligned (same length)
        lengths = [len(seq) for seq in sequences]
        if len(set(lengths)) > 1:
            QMessageBox.warning(
                self,
                "Alignment Error",
                "Sequences must be aligned (same length).\n"
                f"Found sequences with lengths: {', '.join(map(str, set(lengths)))}",
            )
            return

        # Detect or get sequence type
        seq_type = self.detect_sequence_type(sequences)

        try:
            # Get selected mode
            mode = self.mode_combo.currentText()

            # Create position frequency matrix
            pfm = self.create_pfm(sequences, seq_type)

            # Convert to information matrix if needed
            if mode == "Information":
                matrix = self.pfm_to_information(pfm, seq_type)
            else:
                matrix = pfm

            # Generate sequence logo
            self.generate_logo(matrix, seq_type, len(records), mode)

            self.status_label.setText(
                f"Generated: {len(records)} seqs, {lengths[0]} pos ({seq_type} {mode})"
            )
        except Exception as e:
            import traceback

            QMessageBox.critical(
                self,
                "Generation Error",
                f"Failed to generate sequence logo:\n{str(e)}\n\n{traceback.format_exc()}",
            )

    def detect_sequence_type(self, sequences):
        """Detect if sequences are DNA or Protein"""
        choice = self.seq_type_combo.currentText()

        if choice == "DNA":
            return "DNA"
        elif choice == "Protein":
            return "Protein"

        # Auto detect
        dna_chars = set("ATGCNRYKMSWBDHV-")

        all_chars = set()
        for seq in sequences:
            all_chars.update(seq.upper())

        # If all characters are DNA chars, it's DNA
        if all_chars.issubset(dna_chars):
            return "DNA"
        # If contains protein-specific chars, it's protein
        elif not all_chars.issubset(dna_chars):
            return "Protein"
        else:
            return "DNA"  # Default to DNA if unsure

    def create_pfm(self, sequences, seq_type):
        """Create Position Frequency Matrix"""
        # Define valid characters
        if seq_type == "DNA":
            valid_chars = list("ATGC")
        else:  # Protein
            valid_chars = list("ARNDCEQGHILKMFPSTWYV")

        seq_len = len(sequences[0])

        # Create count matrix
        counts = []
        for pos in range(seq_len):
            pos_count = {char: 0 for char in valid_chars}
            for seq in sequences:
                base = seq[pos]
                if base in pos_count:
                    pos_count[base] += 1
                # Ignore gaps and ambiguous characters
            counts.append(pos_count)

        # Convert to DataFrame
        df = pd.DataFrame(counts)

        # Convert counts to probabilities (all-gap columns → uniform; avoids NaN)
        row_sums = df.sum(axis=1)
        zero_sum_mask = row_sums == 0
        df = df.div(row_sums, axis=0)
        # Fill all-gap columns with 0.0 so they contribute zero information.
        if zero_sum_mask.any():
            df.loc[zero_sum_mask] = 0.0

        return df

    def pfm_to_information(self, pfm, seq_type):
        """Convert position frequency matrix to information content matrix"""
        import numpy as np

        # Calculate background frequencies
        if seq_type == "DNA":
            # Equal background for DNA (0.25 each)
            num_bases = 4
        else:  # Protein
            # Equal background for amino acids (0.05 each for 20 aa)
            num_bases = 20

        # Maximum possible entropy
        max_entropy = np.log2(num_bases)

        # Calculate information content for each position
        info_matrix = pfm.copy()

        for idx in pfm.index:
            # Get probabilities for this position
            probs = pfm.loc[idx].values

            # Calculate entropy: H = -sum(p * log2(p)) for p > 0
            entropy = 0
            for p in probs:
                if p > 0:
                    entropy -= p * np.log2(p)

            # Information content = max_entropy - entropy
            information = max_entropy - entropy

            # Scale probabilities by information content
            info_matrix.loc[idx] = probs * information

        return info_matrix

    def generate_logo(self, matrix, seq_type, num_seqs, mode):
        """Generate sequence logo using logomaker"""
        # Clear previous figure
        self.figure.clear()

        # Create axis
        ax = self.figure.add_subplot(111)

        # Create logo
        if seq_type == "DNA":
            logomaker.Logo(matrix, ax=ax, color_scheme="classic")
        else:  # Protein
            logomaker.Logo(matrix, ax=ax, color_scheme="chemistry")

        # Customize plot
        y_label = "Bits" if mode == "Information" else "Probability"
        ax.set_ylabel(y_label, fontsize=14)
        ax.set_xlabel("Position", fontsize=14)
        ax.tick_params(labelsize=12)

        # Set x-axis to show positions starting from 1
        ax.set_xlim((0.5, len(matrix) + 0.5))

        # Keep only left and bottom borders
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax.set_title(
            f"Sequence Logo — {seq_type} ({mode}, {num_seqs} seqs, {len(matrix)} pos)",
            fontsize=13,
            fontweight="bold",
            pad=15,  # more breathing room between title and logo
        )

        # Dynamically widen figure for long sequences so each position is legible
        num_pos = len(matrix)
        if num_pos > 30:
            fig_width = min(15, max(10, num_pos * 0.35))
            self.figure.set_size_inches(fig_width, 3)
        else:
            self.figure.set_size_inches(10, 3)

        # Adjust layout
        self.figure.tight_layout()

        # Lock the scroll area at its current width so the canvas (which may
        # be wider) never inflates the tab or the main window.
        if self._scroll_max_w is None and self._scroll_area.width() > 10:
            self._scroll_max_w = self._scroll_area.width()

        # Size canvas to match the figure at native resolution.
        dpi = self.figure.dpi
        w = int(self.figure.get_figwidth() * dpi)
        h = int(self.figure.get_figheight() * dpi)
        self.canvas.setFixedSize(w, h)
        self._canvas_inner.setFixedSize(w, h)

        if self._scroll_max_w:
            self._scroll_area.setMaximumWidth(self._scroll_max_w)
            self._scroll_area.setMinimumWidth(0)

        # Store current figure for export
        self.current_figure = self.figure

        # Refresh canvas
        self.canvas.draw()

    def export_result(self):
        """Override export to save figure instead of text"""
        if self.current_figure is None:
            QMessageBox.warning(
                self,
                "Export Error",
                "No sequence logo to export. Please generate a logo first.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sequence Logo",
            "sequence_logo.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)",
        )

        if file_path:
            try:
                self.current_figure.savefig(file_path, dpi=300, bbox_inches="tight")
                self.status_label.setText(f"Exported: {os.path.basename(file_path)}")
                self._last_export_dir = os.path.dirname(file_path)
                self.open_folder_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Failed to save figure:\n{str(e)}")

    def clear(self):
        """Clear input, output and figure, restoring the placeholder."""
        self.input_text.clear()
        self.path_edit.clear()
        self._clear_loaded_hint()
        self._draw_placeholder_plot()
        self.current_figure = None
        self.open_folder_btn.setEnabled(False)
        self.status_label.setText("Cleared")

    def _open_output_folder(self):
        """Open the folder of the most recently exported figure."""
        if self._last_export_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

    def show_help(self):
        """Show help dialog."""
        from PyQt6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout

        help_text = """
<h2>Sequence Logo &mdash; Visualize Sequence Conservation</h2>

<p><b>What does this tool do?</b><br>
It generates a sequence logo from a set of aligned DNA or protein sequences.
Each position in the alignment is represented as a stack of letters whose
height reflects how often that letter appears.</p>

<h3>Quick Start</h3>
<ol>
<li>Load aligned sequences in <b>FASTA format</b> with <b>Browse</b> or drag &amp; drop them.</li>
<li>Choose the sequence type (DNA or Protein). Auto-detect works well for most inputs.</li>
<li>Select a display mode (Probability or Information).</li>
<li>Click <b>Run</b> to generate the logo.</li>
<li>Use <b>Save Figure</b> to export as PNG, PDF, or SVG.</li>
</ol>

<h3>Input Requirements</h3>
<ul>
<li>All sequences must have the <b>same length</b> (pre-aligned).</li>
<li>Gap characters (<code>-</code>) are ignored when building the logo.</li>
<li>Use the <b>MSA</b> tools (Muscle5 or MAFFT) to align unaligned sequences first.</li>
</ul>

<h3>Sequence Type</h3>
<ul>
<li><b>DNA</b> — shows A, T, G, C with the classic nucleotide colour scheme
(A green, T red, G orange, C blue).</li>
<li><b>Protein</b> — shows the 20 standard amino acids with a
chemistry-based colour scheme (hydrophobic, polar, charged, etc.).</li>
<li><b>Auto Detect</b> — guesses the type from the letters present.</li>
</ul>

<h3>Display Modes</h3>
<ul>
<li><b>Probability</b> — each letter's height is its observed frequency
at that position (range 0–1). Useful for seeing raw composition.</li>
<li><b>Information</b> — height is scaled by conservation in
<b>bits</b>. A fully conserved column reaches ~2 bits for DNA or
~4.32 bits for proteins. Best for highlighting conserved regions.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>For long sequences the canvas widens automatically; use the horizontal
scrollbar to inspect every position.</li>
<li>Export high-resolution figures (300 DPI) via <b>Save Figure</b>.</li>
<li>Start with a small alignment (5–10 sequences, 20–50 positions) to get
a feel for the output before tackling larger datasets.</li>
</ul>
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Help - Sequence Logo")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml(help_text)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)
        btn = QPushButton(self.tr("Close"))
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()

    def parse_fasta(self, text):
        """Parse FASTA format text"""
        records = []
        lines = text.strip().split("\n")
        current_header = None
        current_seq = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith(">"):
                # Save previous record
                if current_header is not None:
                    seq = "".join(current_seq)
                    if seq:
                        records.append((current_header, seq))

                # Start new record
                current_header = line[1:].strip()
                current_seq = []
            else:
                # Add to current sequence
                current_seq.append(line)

        # Save last record
        if current_header is not None:
            seq = "".join(current_seq)
            if seq:
                records.append((current_header, seq))

        return records
