import re

from Bio.Data import CodonTable
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from modules.fasta_processor import parse_fasta_tuples
from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text

# NCBI genetic code table id, keyed by the human-readable label shown in the combo box.
GENETIC_CODES = {
    "1 - Standard (Universal)": 1,
    "2 - Vertebrate Mitochondrial": 2,
    "3 - Yeast Mitochondrial": 3,
    "4 - Mold / Protozoan / Coelenterate Mitochondrial": 4,
    "5 - Invertebrate Mitochondrial": 5,
    "6 - Ciliate, Dasycladacean and Hexamita Nuclear": 6,
    "9 - Echinoderm and Flatworm Mitochondrial": 9,
    "11 - Bacterial, Archaeal and Plant Plastid": 11,
    "12 - Alternative Yeast Nuclear": 12,
    "13 - Ascidian Mitochondrial": 13,
    "14 - Alternative Flatworm Mitochondrial": 14,
}


def _codon_table_dict(table_id: int) -> dict:
    """Build a codon -> amino-acid dict (stop codons mapped to '*') for an NCBI genetic code id."""
    bt = CodonTable.unambiguous_dna_by_id[table_id]
    table = dict(bt.forward_table)
    for stop in bt.stop_codons:
        table[stop] = "*"
    return table


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
        self.output_text.setPlaceholderText("Translated protein sequence will appear here...")
        self.input_text.setMinimumHeight(150)
        self.output_text.setMinimumHeight(150)

        # Hint label is unused here — hide it so the buttons sit at the
        # bottom of the Input Sequence group
        self.input_hint.hide()

    def _setup_parameters(self):
        """Setup parameter controls in a QGroupBox."""
        grp = QGroupBox("Parameters")
        grp.setFlat(True)
        grid = QGridLayout(grp)
        grid.setContentsMargins(6, 16, 6, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Reading Frame:"), 0, 0)
        self.frame_box = QComboBox()
        self.frame_box.addItems([
            "+1 (forward, from position 1)",
            "+2 (forward, from position 2)",
            "+3 (forward, from position 3)",
            "-1 (reverse complement, from position 1)",
            "-2 (reverse complement, from position 2)",
            "-3 (reverse complement, from position 3)",
        ])
        self.frame_box.setMinimumWidth(320)
        grid.addWidget(self.frame_box, 0, 1)

        grid.addWidget(QLabel("Amino Acid Format:"), 0, 2)
        self.aa_mode_box = QComboBox()
        self.aa_mode_box.addItems([
            "1-letter (e.g., MKTF)",
            "3-letter (e.g., Met-Lys-Thr-Phe)",
        ])
        self.aa_mode_box.setMinimumWidth(200)
        grid.addWidget(self.aa_mode_box, 0, 3)

        grid.addWidget(QLabel("Genetic Code:"), 1, 0)
        self.genetic_code_box = QComboBox()
        self.genetic_code_box.addItems(list(GENETIC_CODES.keys()))
        self.genetic_code_box.setMinimumWidth(320)
        self.genetic_code_box.setToolTip(
            "NCBI genetic code table used for translation. "
            "Choose an alternative (e.g. mitochondrial) code if your "
            "sequence doesn't use the standard code."
        )
        grid.addWidget(self.genetic_code_box, 1, 1)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        # Place the Parameters group between the input and output sections
        self._param_layout.addWidget(grp)

        # Place Example button horizontally with upload_btn (unified pattern)
        self.example_btn = QPushButton("Example")
        self.example_btn.clicked.connect(self._load_example)
        ig_layout = self.input_group.layout()
        ig_layout.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.upload_btn, 1)
        btn_row.addWidget(self.example_btn, 1)
        ig_layout.insertLayout(1, btn_row)

    def _load_example(self):
        """Load the bundled NCBI gyrB CDS example for translation."""
        text = load_example_text("dna", "ncbi_gyrB.fasta")
        if not text:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Example",
                "Failed to load example data. Please check your installation.",
            )
            return
        self.input_text.setPlainText(text)
        self.show_status("Loaded example data: ncbi_gyrB.fasta")

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.show_status("Please enter a DNA or RNA sequence")
            return

        frame = self.frame_box.currentIndex()
        aa_mode = self.aa_mode_box.currentIndex()
        frame_name = self.frame_box.currentText().split()[0]
        genetic_code_id = GENETIC_CODES[self.genetic_code_box.currentText()]
        codon_table = _codon_table_dict(genetic_code_id)

        if ">" in raw:
            records = parse_fasta_tuples(raw, include_gt=True)
            if not records:
                self.show_status("No valid FASTA records found")
                return
            output_blocks = []
            for header, seq in records:
                seq = seq.upper().replace("U", "T")
                if not re.fullmatch(r"[ACGTN]+", seq):
                    self.show_status(f"Invalid characters in {header}: A/T/G/C/N only")
                    return
                trans_seq = self._translate_frame(seq, frame, aa_mode, codon_table)
                output_blocks.append(f"{header} | Frame: {frame_name}\n{trans_seq}")
            self.output_text.setPlainText("\n\n".join(output_blocks))
            self.show_status(f"Translation complete — {len(records)} sequence(s)")
        else:
            seq = raw.replace("\n", "").replace(" ", "").upper().replace("U", "T")
            if not seq:
                self.show_status("No valid sequence found")
                return
            if not re.fullmatch(r"[ACGTN]+", seq):
                self.show_status("Invalid characters. Only A/T/G/C/N allowed")
                return
            trans_seq = self._translate_frame(seq, frame, aa_mode, codon_table)
            self.output_text.setPlainText(trans_seq)
            self.show_status("Translation complete")

    def _translate_frame(self, seq, frame, aa_mode, codon_table):
        if frame < 3:
            return self.translate(seq[frame:], aa_mode, codon_table)
        else:
            revcomp = self.reverse_complement(seq)
            return self.translate(revcomp[frame - 3 :], aa_mode, codon_table)

    def translate(self, seq, aa_mode, codon_table):
        aa_seq = []
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            if len(codon) < 3:
                break
            aa = codon_table.get(codon, "X")
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
(protein) sequences using a selectable genetic code (11 NCBI tables). Supports all six reading
frames and both 1-letter and 3-letter amino acid notation.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste your coding sequence or drag-and-drop a FASTA file</li>
<li>Select a <b>Reading Frame</b> (default +1 works for most CDS (coding sequence) inputs)</li>
<li>Choose <b>Amino Acid Format</b> (1-letter or 3-letter)</li>
<li>Click <b>Run</b> to translate</li>
<li>Export or copy the protein sequence</li>
</ol>

<h3>Reading Frames &mdash; Which One Should I Use?</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Your sequence</b></td><td><b>&rarr; Choose</b></td></tr>
<tr><td>A complete CDS starting at the first nucleotide</td><td>&rarr; <b>+1</b></td></tr>
<tr><td>Genomic DNA &mdash; you don't know where the CDS starts</td><td>&rarr; try all 6 frames with <b>ORF Finder</b></td></tr>
<tr><td>Your gene is on the reverse strand (translated 5'&rarr;3' off the reverse complement)</td><td>&rarr; <b>-1, -2, or -3</b></td></tr>
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
<li>Defaults to the <b>standard (universal) genetic code</b>; choose an alternative from the <b>Genetic Code</b> dropdown (e.g. Vertebrate Mitochondrial, Bacterial/Plant Plastid) for sequences that use a different code</li>
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
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QDialog,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Translate")
        dialog.resize(600, 480)
        dialog.setMinimumSize(400, 300)
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
