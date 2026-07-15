from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text
import re
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QMessageBox, QGroupBox


class ComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        "ACGTacgtRYMKSWBDHVNrykmswbdhvn",
        "TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn",
    )

    def __init__(self, parent=None):
        super().__init__("Complement/Reverse Complement", "sequence")
        self._setup_mode_controls()
        self.input_text.setPlaceholderText(
            "Paste DNA sequence in FASTA format (single or multiple sequences) "
            "or drag-and-drop a file...\n"
            "Examples:\n"
            ">seq1\n"
            "ATGCGATCGATCG\n"
            ">seq2\n"
            "TTAAGGCCTTAAGG"
        )
        self._update_output_placeholder()
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
        """Load the bundled 16S primers DNA example."""
        text = load_example_text("dna", "16s_primers.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("Loaded example data: 16s_primers.fasta"))

    def _setup_mode_controls(self):
        grp = QGroupBox(self.tr("Mode"))
        grp.setFlat(True)
        mode_layout = QHBoxLayout(grp)
        mode_layout.setContentsMargins(0, 16, 0, 4)
        mode_layout.addWidget(QLabel(self.tr("Mode:")))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Complement", "Reverse Complement"])
        self.mode_combo.setMinimumWidth(220)
        self.mode_combo.currentTextChanged.connect(self._update_output_placeholder)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        self.add_content_widget(grp)

    def _update_output_placeholder(self):
        if self.mode_combo.currentText() == "Reverse Complement":
            self.output_text.setPlaceholderText("Reverse complement sequences will appear here...")
        else:
            self.output_text.setPlaceholderText("Complement sequences will appear here...")

    def set_mode(self, mode: str):
        index = self.mode_combo.findText(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

    def _transform_sequence(self, sequence: str) -> str:
        transformed = sequence.translate(self.complement_map)
        if self.mode_combo.currentText() == "Reverse Complement":
            return transformed[::-1]
        return transformed

    def _mode_label(self) -> str:
        return self.mode_combo.currentText().lower()

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.show_status("Please enter a DNA sequence or FASTA.")
            return

        if ">" in seq:
            result = self._convert_fasta(seq)
            if result:
                self.output_text.setPlainText(result)
                self.show_status(f"Generated {self._mode_label()} for FASTA input")
            else:
                self.show_status("Invalid FASTA format or sequences")
        else:
            if not self.is_valid_dna(seq):
                self.show_status("Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc.")
                return
            transformed = self._transform_sequence(seq)
            self.output_text.setPlainText(transformed)
            self.show_status(f"{self.mode_combo.currentText()} generated")

    def _convert_fasta(self, fasta_text):
        """Convert FASTA format DNA with the selected mode."""
        lines = fasta_text.split("\n")
        output_lines = []
        current_seq = []
        current_header = None

        for line in lines:
            line = line.strip()
            if line.startswith(">"):
                if current_header is not None and current_seq:
                    seq = "".join(current_seq)
                    if self.is_valid_dna(seq):
                        transformed = self._transform_sequence(seq)
                        output_lines.append(current_header)
                        output_lines.append(transformed)
                    else:
                        return None
                current_header = line
                current_seq = []
            elif line:
                current_seq.append(line)

        if current_header is not None and current_seq:
            seq = "".join(current_seq)
            if self.is_valid_dna(seq):
                transformed = self._transform_sequence(seq)
                output_lines.append(current_header)
                output_lines.append(transformed)
            else:
                return None

        return "\n".join(output_lines) if output_lines else None

    def is_valid_dna(self, seq):
        return re.fullmatch(r"[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+", seq) is not None

    def show_help(self):
        help_text = """
<h2>Complement / Reverse Complement &mdash; DNA Strand Transformations</h2>

<p><b>What does this tool do?</b><br>
It generates the complementary strand of a DNA sequence. Choose <b>Complement</b>
to replace each base with its pairing partner, or <b>Reverse Complement</b> to
also reverse the sequence (5'&rarr;3' to 3'&rarr;5'), which is essential for
primer design and cloning workflows.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste DNA sequence(s) or drag-and-drop a FASTA file</li>
<li>Choose <b>Complement</b> or <b>Reverse Complement</b> from the dropdown</li>
<li>Click <b>Run</b></li>
<li>Export or copy the result</li>
</ol>

<h3>When to Use Each Mode</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Your goal</b></td><td><b>&rarr; Choose</b></td></tr>
<tr><td>See what the opposite strand looks like without changing direction</td><td>&rarr; <b>Complement</b></td></tr>
<tr><td>Design a reverse primer or antisense oligo</td><td>&rarr; <b>Reverse Complement</b></td></tr>
<tr><td>Convert a reverse-complemented hit back to the forward strand</td><td>&rarr; <b>Reverse Complement</b> again</td></tr>
</table>

<h3>Base-Pairing Rules</h3>
<table border="0" cellpadding="2" cellspacing="4">
<tr><td>A &harr; T</td><td>G &harr; C</td><td>N &rarr; N</td></tr>
<tr><td>R &harr; Y</td><td>M &harr; K</td><td>S &rarr; S</td></tr>
<tr><td>W &rarr; W</td><td>B &harr; V</td><td>D &harr; H</td></tr>
</table>

<h3>Example</h3>
<pre>
Input:
>seq1
ATGCGATCG

Complement:
>seq1
TACGCTAGC

Reverse Complement:
>seq1
CGATCGCAT
</pre>

<h3>Tips</h3>
<ul>
<li>Sequence orientation matters &mdash; the reverse complement of the reverse complement gives you back the original</li>
<li>For primer work: the reverse primer sequence you order is the reverse complement of your template</li>
<li>Multi-FASTA input is supported &mdash; each sequence is transformed independently</li>
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
        dialog.setWindowTitle("Help - Complement/Reverse Complement")
        dialog.setFixedSize(800, 600)
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
