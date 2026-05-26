from PyQt6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDialog,
    QTextBrowser,
    QPushButton,
)
from utils.common_components import BaseTabWidget
import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd
import logomaker


class SequenceLogoTab(BaseTabWidget):
    """Sequence Logo Tab - Generate sequence logos for DNA or protein sequences"""

    def __init__(self, parent=None):
        super().__init__("Sequence Logo (Logomaker)", "sequence")

        # Customize UI elements
        self.run_btn.setText("Generate Logo")
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()  # Hide copy button for this tab
        if hasattr(self, "export_btn"):
            self.export_btn.hide()

        # Update placeholders
        self.input_text.setPlaceholderText(
            "Paste aligned sequences in FASTA format or drag-and-drop a file...\n\n"
            "Examples:\n"
            "DNA sequences:\n"
            ">seq1\nATGCATGC\n"
            ">seq2\nATGCATGC\n"
            ">seq3\nATGCATGT\n\n"
            "Protein sequences:\n"
            ">prot1\nMKTFFVAG\n"
            ">prot2\nMKTFFVAG\n"
            ">prot3\nMKTFFVSG"
        )
        self.output_text.hide()  # Hide text output area
        self.output_label.hide()
        self.input_hint.hide()

        # Add sequence type selector and mode selector
        self.add_sequence_type_selector()
        self.add_mode_selector()

        # Add matplotlib canvas
        self.add_plot_canvas()

        # Enable drag-and-drop
        self._setup_drag_drop()

        # Store current figure for export
        self.current_figure = None

    def _clear_loaded_hint(self):
        self.input_hint.clear()
        self.input_hint.hide()

    def open_file(self):
        super().open_file()
        self._clear_loaded_hint()

    def add_sequence_type_selector(self):
        """Add sequence type selector"""
        type_layout = QHBoxLayout()
        type_label = QLabel("Sequence Type:")
        self.seq_type_combo = QComboBox()
        self.seq_type_combo.addItems(["Auto Detect", "DNA", "Protein"])
        self.seq_type_combo.setCurrentIndex(0)

        type_layout.addWidget(type_label)
        type_layout.addWidget(self.seq_type_combo)
        type_layout.addStretch()

        # Insert before run button
        self.content_area.insertLayout(self.content_area.count() - 1, type_layout)

    def add_mode_selector(self):
        """Add mode selector for probability vs information"""
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Display Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Probability", "Information"])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip(
            "Probability: Shows frequency of each base/residue at each position\n"
            "Information: Shows information content (bits) based on sequence conservation"
        )

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()

        # Insert before run button
        self.content_area.insertLayout(self.content_area.count() - 1, mode_layout)

    def add_plot_canvas(self):
        """Add matplotlib canvas for displaying sequence logo"""
        # Create figure and canvas
        self.figure = Figure(figsize=(10, 3))
        self.canvas = FigureCanvas(self.figure)

        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Create layout for plot
        plot_layout = QVBoxLayout()
        plot_label = QLabel("Sequence Logo:")
        plot_layout.addWidget(plot_label)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)

        # Insert before control buttons
        self.content_area.insertLayout(self.content_area.count() - 1, plot_layout)

    def run(self):
        """Generate sequence logo"""
        self.status_label.setText("")
        text = self.input_text.toPlainText().strip()

        if not text:
            QMessageBox.warning(
                self, "Input Error", "Please input or load FASTA sequences."
            )
            return

        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "Format Error", str(e))
            return

        if not records:
            QMessageBox.warning(
                self, "Input Error", "No valid FASTA sequences detected."
            )
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
                f"Generated sequence logo for {len(records)} sequences "
                f"({seq_type}, {mode} mode, length: {lengths[0]} positions)"
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

        # Convert counts to probabilities
        df = df.div(df.sum(axis=1), axis=0)

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
        ax.set_ylabel(y_label, fontsize=12)
        ax.set_xlabel("Position", fontsize=12)
        ax.set_title(
            f"{seq_type} Sequence Logo - {mode} (n={num_seqs})",
            fontsize=14,
            fontweight="bold",
        )

        # Set x-axis to show positions starting from 1
        ax.set_xlim((0.5, len(matrix) + 0.5))

        # Adjust layout
        self.figure.tight_layout()

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
                self.status_label.setText(f"Figure saved: {file_path}")
            except Exception as e:
                QMessageBox.warning(
                    self, "Export Error", f"Failed to save figure:\n{str(e)}"
                )

    def clear(self):
        """Clear input, output and figure"""
        self.input_text.clear()
        self._clear_loaded_hint()
        self.figure.clear()
        self.canvas.draw()
        self.current_figure = None
        self.status_label.setText("Cleared")

    def show_help(self):
        """Show help dialog"""
        help_text = """
<h3>Sequence Logo Generator</h3>

<p><b>Purpose:</b> Generate sequence logos to visualize sequence conservation patterns in aligned DNA or protein sequences.</p>

<p><b>Input Format:</b></p>
<ul>
<li>Aligned sequences in FASTA format</li>
<li>All sequences must have the same length</li>
<li>Gaps (-) are ignored in the logo</li>
</ul>

<p><b>Sequence Types:</b></p>
<ul>
<li><b>DNA:</b> Displays nucleotides (A, T, G, C) with classic color scheme</li>
<li><b>Protein:</b> Displays amino acids with chemistry-based color scheme</li>
<li><b>Auto Detect:</b> Automatically determines sequence type</li>
</ul>

<p><b>Display Modes:</b></p>
<ul>
<li><b>Probability:</b> Shows the frequency/probability of each base or amino acid at each position. The height of each letter represents its probability (0-1).</li>
<li><b>Information:</b> Shows the information content (in bits) at each position. Higher values indicate greater conservation. The total height reflects sequence conservation (max 2 bits for DNA, ~4.32 bits for proteins).</li>
</ul>

<p><b>Output:</b></p>
<ul>
<li>Interactive sequence logo plot</li>
<li>Height of letters indicates probability/frequency (Probability mode) or information content (Information mode)</li>
<li>Use toolbar to zoom, pan, or save the figure</li>
</ul>

<p><b>Export:</b> Save the logo as PNG, PDF, or SVG format (high resolution, 300 DPI)</p>

<p><b>Example DNA sequences:</b></p>
<pre>
>seq1
ATGCATGC
>seq2
ATGCATGC
>seq3
ATGCATGT
</pre>

<p><b>Note:</b> This is a local implementation using the logomaker Python package.</p>
        """

        # Create custom dialog with wider width
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Sequence Logo (Logomaker)")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(500)

        layout = QVBoxLayout()

        # Text browser for HTML content
        text_browser = QTextBrowser()
        text_browser.setHtml(help_text)
        text_browser.setOpenExternalLinks(True)
        layout.addWidget(text_browser)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)
        dialog.exec()

    def _setup_drag_drop(self):
        """Setup drag and drop for file loading"""
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
                    self._clear_loaded_hint()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))

        self.input_text.dragEnterEvent = drag_enter
        self.input_text.dropEvent = drop

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
