from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text
import re
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QGroupBox

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
        self._setup_parameters()
        self.input_text.setPlaceholderText(
            "Paste one or more DNA/RNA sequences in FASTA format "
            "or drag-and-drop a file...\n"
            "Example:\n"
            ">seq1\n"
            "ATGCGATCGATCGTAA\n"
            ">seq2\n"
            "ATGAAATTTGGGTGA"
        )
        self.output_text.setPlaceholderText(
            "Translated protein sequence will appear here..."
        )
        self.input_text.setMinimumHeight(150)
        self.output_text.setMinimumHeight(150)

    def _setup_parameters(self):
        """Setup parameter controls in a QGroupBox."""
        grp = QGroupBox(self.tr("Parameters"))
        grp.setFlat(True)
        params_layout = QHBoxLayout(grp)
        params_layout.setContentsMargins(0, 16, 0, 4)

        params_layout.addWidget(QLabel(self.tr("Reading Frame:")))
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
        params_layout.addWidget(self.frame_box)
        params_layout.addSpacing(20)

        params_layout.addWidget(QLabel(self.tr("Amino Acid Format:")))
        self.aa_mode_box = QComboBox()
        self.aa_mode_box.addItems([
            "1-letter (e.g., MKTF)",
            "3-letter (e.g., Met-Lys-Thr-Phe)",
        ])
        self.aa_mode_box.setMinimumWidth(200)
        params_layout.addWidget(self.aa_mode_box)
        params_layout.addStretch()

        self.add_content_widget(grp)

        # Place Example button horizontally with upload_btn (unified pattern)
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ig_layout = self.input_group.layout()
        ig_layout.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.upload_btn, 1)
        btn_row.addWidget(self.example_btn, 1)
        ig_layout.insertLayout(1, btn_row)

    def _load_example(self):
        """Load the first CDS record of the cytb example for translation."""
        text = load_example_text("phylo", "cytb_cds_aligned.fasta")
        if not text:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        # keep only the first FASTA record
        first = text.split("\n>", 1)[0]
        if not first.startswith(">"):
            first = ">" + first
        self.input_text.setPlainText(first.strip() + "\n")
        self.show_status(self.tr("已载入示例数据: cytb_cds (首条记录)"))

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText("Please enter a DNA or RNA sequence.")
            return

        frame = self.frame_box.currentIndex()
        aa_mode = self.aa_mode_box.currentIndex()
        frame_name = self.frame_box.currentText().split()[0]

        if ">" in raw:
            records = self._parse_fasta(raw)
            if not records:
                self.status_label.setText("No valid FASTA records found.")
                return
            output_blocks = []
            for header, seq in records:
                seq = seq.upper().replace("U", "T")
                if not re.fullmatch(r"[ACGTN]+", seq):
                    self.status_label.setText(
                        f"Invalid characters in {header}. Only A/T/G/C/N allowed."
                    )
                    return
                trans_seq = self._translate_frame(seq, frame, aa_mode)
                output_blocks.append(f"{header} | Frame: {frame_name}\n{trans_seq}")
            self.output_text.setPlainText("\n\n".join(output_blocks))
            self.status_label.setText(
                f"Translation complete — {len(records)} sequence(s)"
            )
        else:
            seq = raw.replace("\n", "").replace(" ", "").upper().replace("U", "T")
            if not seq:
                self.status_label.setText("No valid sequence found.")
                return
            if not re.fullmatch(r"[ACGTN]+", seq):
                self.status_label.setText("Invalid characters. Only A/T/G/C/N allowed.")
                return
            trans_seq = self._translate_frame(seq, frame, aa_mode)
            self.output_text.setPlainText(trans_seq)
            self.status_label.setText("Translation complete")

    def _parse_fasta(self, text):
        records = []
        header = None
        seq_lines = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(">"):
                if header is not None:
                    records.append((header, "".join(seq_lines)))
                header = line
                seq_lines = []
            elif line:
                seq_lines.append(line)
        if header is not None:
            records.append((header, "".join(seq_lines)))
        return records

    def _translate_frame(self, seq, frame, aa_mode):
        if frame < 3:
            return self.translate(seq[frame:], aa_mode)
        else:
            revcomp = self.reverse_complement(seq)
            return self.translate(revcomp[frame - 3 :], aa_mode)

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
<h2>Translate &mdash; DNA/RNA to Protein Translation</h2>

<p><b>What does this tool do?</b><br>
It translates DNA or RNA coding sequences into their corresponding amino acid
(protein) sequences using the standard genetic code. Supports all six reading
frames and both 1-letter and 3-letter amino acid notation.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste your coding sequence or drag-and-drop a FASTA file</li>
<li>Select a <b>Reading Frame</b> (default +1 works for most CDS inputs)</li>
<li>Choose <b>Amino Acid Format</b> (1-letter or 3-letter)</li>
<li>Click <b>Run</b> to translate</li>
<li>Export or copy the protein sequence</li>
</ol>

<h3>Reading Frames &mdash; Which One Should I Use?</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Your sequence</b></td><td><b>&rarr; Choose</b></td></tr>
<tr><td>A complete CDS starting at the first nucleotide</td><td>&rarr; <b>+1</b></td></tr>
<tr><td>Genomic DNA &mdash; you don't know where the CDS starts</td><td>&rarr; try all 6 frames with <b>ORF Finder</b></td></tr>
<tr><td>You have the reverse-complemented sequence</td><td>&rarr; <b>-1, -2, or -3</b></td></tr>
</table>

<h3>Amino Acid Formats</h3>
<ul>
<li><b>1-letter</b> &mdash; compact, standard in bioinformatics (e.g. <code>MKTFG*</code>)</li>
<li><b>3-letter</b> &mdash; human-readable, separated by dashes (e.g. <code>Met-Lys-Thr-Phe-Gly-Stop</code>)</li>
</ul>

<h3>Example</h3>
<pre>
Input DNA:
ATGAAATTTGGGTGA

Translation (+1, 1-letter):
MKFG*

Translation (+1, 3-letter):
Met-Lys-Phe-Gly-Stop
</pre>

<h3>Genetic Code Notes</h3>
<ul>
<li>Uses the <b>standard (universal) genetic code</b></li>
<li>RNA input (U) is automatically treated as DNA (T)</li>
<li>Stop codons: <code>*</code> (1-letter) or <code>Stop</code> (3-letter)</li>
<li>Incomplete codons at the 3' end are silently ignored</li>
<li>Unknown codons are shown as <code>X</code> / <code>Xxx</code></li>
</ul>

<h3>Tips</h3>
<ul>
<li>If your sequence doesn't translate as expected, check the reading frame &mdash; shifting by 1 or 2 bases can make all the difference</li>
<li>Use <b>ORF Finder</b> first if you're working with genomic DNA and need to locate coding regions</li>
<li>Multi-FASTA input is supported &mdash; each record is translated independently</li>
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
        dialog.setWindowTitle("Help - Translate")
        dialog.setFixedSize(820, 620)
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
