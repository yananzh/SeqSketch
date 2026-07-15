from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text
from PyQt6.QtWidgets import QPushButton, QHBoxLayout, QMessageBox
import re


class RNATab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Convert to RNA", "sequence")
        self.input_text.setPlaceholderText(
            "Paste DNA sequence in FASTA format (single or multiple sequences) "
            "or drag-and-drop a file...\n"
            "Examples:\n"
            ">seq1\n"
            "ATGCGATCGATCG\n"
            ">seq2\n"
            "TTAAGGCCTTAAGG"
        )
        self.output_text.setPlaceholderText("RNA sequences will appear here...")
        self.input_text.setMinimumHeight(150)
        self.output_text.setMinimumHeight(150)

        # Place Example button horizontally with upload_btn
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ig_layout = self.input_group.layout()
        ig_layout.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.upload_btn, 1)
        btn_row.addWidget(self.example_btn, 1)
        ig_layout.insertLayout(1, btn_row)

    def _load_example(self):
        """Load the bundled HBB exon 1 DNA example."""
        text = load_example_text("dna", "hbb_exon1.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("Loaded example data: hbb_exon1.fasta"))

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.show_status("Please enter a DNA sequence or FASTA.")
            return

        # Check if input is FASTA format
        if ">" in seq:
            # Parse and convert multi-sequence FASTA
            result = self._convert_fasta(seq)
            if result:
                self.output_text.setPlainText(result)
                self.show_status("Converted FASTA to RNA")
            else:
                self.show_status("Invalid FASTA format or sequences")
        else:
            # Single raw sequence
            if not self.is_valid_dna(seq):
                self.show_status("Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc.")
                return
            rna = seq.upper().replace("T", "U").replace("t", "u")
            self.output_text.setPlainText(rna)
            self.show_status("Converted to RNA")

    def _convert_fasta(self, fasta_text):
        """Convert FASTA format DNA to RNA"""
        lines = fasta_text.split("\n")
        output_lines = []
        current_seq = []
        current_header = None

        for line in lines:
            line = line.strip()
            if line.startswith(">"):
                # Save previous sequence if exists
                if current_header is not None and current_seq:
                    seq = "".join(current_seq)
                    if self.is_valid_dna(seq):
                        rna = seq.upper().replace("T", "U").replace("t", "u")
                        output_lines.append(current_header)
                        output_lines.append(rna)
                    else:
                        return None
                # Start new sequence
                current_header = line
                current_seq = []
            elif line:
                current_seq.append(line)

        # Save last sequence
        if current_header is not None and current_seq:
            seq = "".join(current_seq)
            if self.is_valid_dna(seq):
                rna = seq.upper().replace("T", "U").replace("t", "u")
                output_lines.append(current_header)
                output_lines.append(rna)
            else:
                return None

        return "\n".join(output_lines) if output_lines else None

    def is_valid_dna(self, seq):
        # Allow IUPAC nucleotide codes (incl. U — already-RNA input is accepted unchanged)
        return re.fullmatch(r"[ACGTUNacgtunRYMKSWBDHVrykmswbdhv\s]+", seq) is not None

    def show_help(self):
        help_text = """
<h2>Convert to RNA &mdash; Replace Thymine (T) with Uracil (U)</h2>

<p><b>What does this tool do?</b><br>
It converts DNA sequences to RNA by replacing every T (Thymine) with U (Uracil).
Supports single sequences, multi-sequence FASTA files, and IUPAC ambiguous
nucleotide codes.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste DNA sequence(s) or drag-and-drop a FASTA file</li>
<li>Click <b>Run</b> to convert</li>
<li>Export or copy the RNA result</li>
</ol>

<h3>Input Formats</h3>
<ul>
<li><b>Raw sequence</b> &mdash; plain DNA text (e.g. <code>ATGCGATCG</code>)</li>
<li><b>FASTA single</b> &mdash; <code>&gt;header</code> followed by sequence</li>
<li><b>FASTA multi</b> &mdash; multiple sequences with headers, each converted independently</li>
</ul>

<h3>Supported Characters</h3>
<p>All IUPAC nucleotide codes are recognised and passed through unchanged
(only T &rarr; U is transformed):</p>
<p><code>A C G T U N R Y M K S W B D H V</code> (case-insensitive)</p>

<h3>Example</h3>
<pre>
Input:
>seq1
ATGCGATCG
>seq2
TTAAGGCC

Output:
>seq1
AUGCGAUCG
>seq2
UUAAGGCC
</pre>

<h3>Tips</h3>
<ul>
<li>Already an RNA sequence? The tool is safe &mdash; existing U characters are left unchanged</li>
<li>Working with large multi-FASTA files? Use <b>Export Result</b> to save to a .fasta file</li>
<li>IUPAC codes (R, Y, M, etc.) are preserved; only A/T/G/C are subject to T &rarr; U conversion</li>
</ul>
        """
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )
        from PyQt6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Convert to RNA")
        dialog.setFixedSize(780, 580)
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
