from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox, QComboBox, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

CODON_TABLE = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}
AA_3LETTER = {
    "A": "Ala",
    "R": "Arg",
    "N": "Asn",
    "D": "Asp",
    "C": "Cys",
    "Q": "Gln",
    "E": "Glu",
    "G": "Gly",
    "H": "His",
    "I": "Ile",
    "L": "Leu",
    "K": "Lys",
    "M": "Met",
    "F": "Phe",
    "P": "Pro",
    "S": "Ser",
    "T": "Thr",
    "W": "Trp",
    "Y": "Tyr",
    "V": "Val",
    "*": "Stop",
}


class TranslateTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Translate", "sequence")
        self._setup_drag_drop()
        self._update_ui_layout()
        self._setup_parameters()

    def _setup_drag_drop(self):
        """Enable drag-and-drop for FASTA files"""
        self.input_text.setAcceptDrops(True)
        self.input_text.dragEnterEvent = self._drag_enter_event
        self.input_text.dropEvent = self._drop_event

    def _drag_enter_event(self, event):
        """Handle drag enter for file drops"""
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_event(self, event):
        """Handle file drop for FASTA input"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Keep full content including headers
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"Loaded file: {file_path}")
                event.acceptProposedAction()
            except Exception as e:
                self.status_label.setText(f"Error loading file: {e}")
                event.ignore()

    def _update_ui_layout(self):
        """Update placeholder and input/output sizing"""
        self.input_text.setPlaceholderText(
            "Paste DNA/RNA sequence in FASTA format (single sequence only) or drag-and-drop a file...\n"
            "Example:\n"
            ">seq1\n"
            "ATGCGATCGATCGTAA"
        )
        self.input_hint.setText(
            "Single sequence only. Use one DNA/RNA record per run; FASTA header is preserved in the output."
        )
        self.output_text.setPlaceholderText(
            "Translated protein sequence will appear here..."
        )
        # Adjust minimum heights for better visibility
        self.input_text.setMinimumHeight(180)
        self.output_text.setMinimumHeight(180)

    def _setup_parameters(self):
        """Setup parameter controls with labels"""
        # Reading frame selection
        frame_layout = QHBoxLayout()
        frame_label = QLabel("Reading Frame:")
        self.frame_box = QComboBox()
        self.frame_box.addItems([
            "+1 (forward, from position 1)",
            "+2 (forward, from position 2)",
            "+3 (forward, from position 3)",
            "-1 (reverse complement, from position 1)",
            "-2 (reverse complement, from position 2)",
            "-3 (reverse complement, from position 3)",
        ])
        self.frame_box.setMinimumWidth(280)
        frame_layout.addWidget(frame_label)
        frame_layout.addWidget(self.frame_box)
        frame_layout.addStretch()

        # Amino acid notation
        aa_layout = QHBoxLayout()
        aa_label = QLabel("Amino Acid Format:")
        self.aa_mode_box = QComboBox()
        self.aa_mode_box.addItems([
            "1-letter (e.g., MKTF)",
            "3-letter (e.g., Met-Lys-Thr-Phe)",
        ])
        self.aa_mode_box.setMinimumWidth(240)
        aa_layout.addWidget(aa_label)
        aa_layout.addWidget(self.aa_mode_box)
        aa_layout.addStretch()

        self.add_content_layout(frame_layout)
        self.add_content_layout(aa_layout)

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA or RNA sequence.")
            return

        # Parse FASTA if present
        header = None
        if ">" in seq:
            lines = seq.split("\n")
            seq_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith(">"):
                    header = line
                elif line:
                    seq_lines.append(line)
            seq = "".join(seq_lines)

        # Clean sequence
        seq = seq.replace("\n", "").replace(" ", "").upper().replace("U", "T")

        if not seq:
            self.status_label.setText("No valid sequence found.")
            return

        if not re.fullmatch(r"[ACGTN]+", seq):
            self.status_label.setText("Invalid characters. Only A/T/G/C/N allowed.")
            return

        frame = self.frame_box.currentIndex()
        aa_mode = self.aa_mode_box.currentIndex()

        if frame < 3:
            offset = frame
            trans_seq = self.translate(seq[offset:], aa_mode)
        else:
            offset = frame - 3
            revcomp = self.reverse_complement(seq)
            trans_seq = self.translate(revcomp[offset:], aa_mode)

        # Add header to output if present
        if header:
            frame_name = self.frame_box.currentText().split()[0]
            output = f"{header} | Frame: {frame_name}\n{trans_seq}"
        else:
            output = trans_seq

        self.output_text.setPlainText(output)
        self.status_label.setText("Translation complete")

    def translate(self, seq, aa_mode):
        aa_seq = []
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            if len(codon) < 3:
                break
            aa = CODON_TABLE.get(codon, "X")
            if aa_mode == 0:
                aa_seq.append(aa)
            else:
                aa_seq.append(AA_3LETTER.get(aa, "Xxx"))
        return "-".join(aa_seq) if aa_mode == 1 else "".join(aa_seq)

    def reverse_complement(self, seq):
        comp_map = str.maketrans("ACGT", "TGCA")
        return seq.translate(comp_map)[::-1]

    def show_help(self):
        help_text = """
<h3>DNA/RNA Translation</h3>
<p><b>Description:</b></p>
<p>Translate DNA or RNA sequences to protein using the standard genetic code. Supports all 6 reading frames and multiple amino acid formats.</p>

<p><b>Usage:</b></p>
<ol>
<li>Paste sequence or drag-and-drop a FASTA file (single sequence only)</li>
<li>Select reading frame (+1/+2/+3 for forward, -1/-2/-3 for reverse complement)</li>
<li>Choose amino acid format (1-letter or 3-letter notation)</li>
<li>Click "Run" to translate</li>
<li>Export or copy the protein sequence</li>
</ol>

<p><b>Reading Frames:</b></p>
<ul>
<li><b>+1, +2, +3:</b> Forward strand starting at position 1, 2, or 3</li>
<li><b>-1, -2, -3:</b> Reverse complement strand starting at position 1, 2, or 3</li>
</ul>

<p><b>Amino Acid Formats:</b></p>
<ul>
<li><b>1-letter:</b> Single character (e.g., M K T F)</li>
<li><b>3-letter:</b> Three characters separated by dashes (e.g., Met-Lys-Thr-Phe)</li>
</ul>

<p><b>Example:</b></p>
<pre>
Input DNA:
ATGAAATTTGGG

Translation (+1, 1-letter):
MKFG

Translation (+1, 3-letter):
Met-Lys-Phe-Gly
</pre>

<p><b>Notes:</b></p>
<ul>
<li>Uses standard genetic code</li>
<li>Stop codons shown as * (1-letter) or Stop (3-letter)</li>
<li>RNA (U) automatically converted to DNA (T)</li>
<li>Incomplete codons at the end are ignored</li>
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
        dialog.setWindowTitle("Help - Translate")
        dialog.setFixedSize(700, 550)
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
