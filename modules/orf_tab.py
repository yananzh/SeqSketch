from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QSpinBox, QComboBox, QHBoxLayout, QLabel

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


class ORFTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("ORF Finder", "sequence")
        self._setup_parameters()
        self.input_text.setPlaceholderText(
            "Paste DNA sequence in FASTA format (single sequence only) "
            "or drag-and-drop a file...\n"
            "Example:\n"
            ">seq1\n"
            "ATGAAACCCGGGTTTAAATAG"
        )
        self.output_text.setPlaceholderText("ORF results will appear here...")
        self.input_text.setMinimumHeight(180)
        self.output_text.setMinimumHeight(220)

    def _setup_parameters(self):
        """Setup parameter controls in a single horizontal row."""
        params_layout = QHBoxLayout()

        params_layout.addWidget(QLabel("Min ORF Length:"))
        self.min_len_box = QSpinBox()
        self.min_len_box.setRange(30, 10000)
        self.min_len_box.setValue(100)
        self.min_len_box.setSuffix(" nt")
        self.min_len_box.setMinimumWidth(100)
        params_layout.addWidget(self.min_len_box)
        params_layout.addSpacing(16)

        params_layout.addWidget(QLabel("Search Strand:"))
        self.chain_box = QComboBox()
        self.chain_box.addItems([
            "Forward strand only",
            "Reverse strand only",
            "Both strands",
        ])
        self.chain_box.setCurrentIndex(2)
        self.chain_box.setMinimumWidth(160)
        params_layout.addWidget(self.chain_box)
        params_layout.addSpacing(16)

        params_layout.addWidget(QLabel("Start Codons:"))
        self.start_codon_box = QComboBox()
        self.start_codon_box.addItems([
            "ATG only (standard)",
            "ATG, GTG, TTG (alternative)",
        ])
        self.start_codon_box.setMinimumWidth(200)
        params_layout.addWidget(self.start_codon_box)
        params_layout.addStretch()

        self.add_content_layout(params_layout)

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA sequence.")
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

        min_len = self.min_len_box.value()
        chain_mode = self.chain_box.currentIndex()
        use_alt_start = self.start_codon_box.currentIndex() == 1
        results = []
        if chain_mode in (0, 2):
            results += self.find_orfs(seq, "+", use_alt_start)
        if chain_mode in (1, 2):
            revcomp = self.reverse_complement(seq)
            results += self.find_orfs(revcomp, "-", use_alt_start)
        results = [orf for orf in results if orf["length"] >= min_len]
        if not results:
            self.output_text.setPlainText("No ORFs meet the criteria.")
            self.status_label.setText("No ORF")
            return

        # Format output with header if present
        out = []
        if header:
            out.append(f"{header}\n")
        for idx, orf in enumerate(results, 1):
            out.append(
                f"ORF #{idx} | Frame: {orf['frame']} | Position: {orf['start'] + 1}-{orf['end']} | Length: {orf['length']} nt\nSequence: {orf['seq']}\nTranslation: {orf['aa']}\n"
            )
        self.output_text.setPlainText("\n".join(out))
        self.status_label.setText(f"Found {len(results)} ORFs")

    def find_orfs(self, seq, strand, use_alt_start=False):
        orfs = []
        start_codons = ["ATG", "GTG", "TTG"] if use_alt_start else ["ATG"]
        for frame in range(3):
            i = frame
            while i < len(seq) - 2:
                codon = seq[i : i + 3]
                if codon in start_codons:
                    for j in range(i + 3, len(seq) - 2, 3):
                        stop = seq[j : j + 3]
                        if stop in ("TAA", "TAG", "TGA"):
                            orf_seq = seq[i : j + 3]
                            aa = self.translate(orf_seq)
                            orfs.append({
                                "frame": f"{strand}{frame + 1}",
                                "start": i if strand == "+" else len(seq) - j - 2,
                                "end": j + 3 if strand == "+" else len(seq) - i,
                                "length": len(orf_seq),
                                "seq": orf_seq,
                                "aa": aa,
                            })
                            i = j + 3
                            break
                    else:
                        i += 3
                else:
                    i += 3
        return orfs

    def translate(self, seq):
        aa_seq = []
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            aa = CODON_TABLE.get(codon, "X")
            aa_seq.append(aa)
        return "".join(aa_seq)

    def reverse_complement(self, seq):
        comp_map = str.maketrans("ACGT", "TGCA")
        return seq.translate(comp_map)[::-1]

    def show_help(self):
        help_text = """
<h2>ORF Finder &mdash; Open Reading Frame Detection</h2>

<p><b>What does this tool do?</b><br>
It scans a DNA sequence in all six reading frames and reports every open reading
frame (ORF) &mdash; regions that start with a start codon and end with an in-frame
stop codon. This is a core tool for gene prediction and coding-region
identification.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste your DNA sequence or drag-and-drop a FASTA file</li>
<li>Set the <b>minimum ORF length</b> (default 100 nt &mdash; shorter values find more ORFs but increase noise)</li>
<li>Choose the <b>search strand</b> (both strands is recommended)</li>
<li>Choose <b>start codons</b> (standard ATG or include alternative starts)</li>
<li>Click <b>Run</b> to find ORFs</li>
</ol>

<h3>Parameter Guide</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Parameter</b></td><td><b>What it controls</b></td></tr>
<tr><td>Min ORF Length</td><td>Filters out short ORFs. For bacterial genomes 100 nt is typical; for eukaryotes try 300 nt.</td></tr>
<tr><td>Search Strand</td><td><b>Both strands</b> = all 6 reading frames (best for discovery). <b>Forward only</b> = 3 frames on the + strand.</td></tr>
<tr><td>Start Codons</td><td><b>ATG only</b> for eukaryotes. <b>ATG/GTG/TTG</b> for bacteria where alternative starts are common.</td></tr>
</table>

<h3>Understanding the Output</h3>
<ul>
<li><b>ORF #</b> &mdash; sequential number for easy reference</li>
<li><b>Frame</b> &mdash; reading frame (+1/+2/+3 = forward, -1/-2/-3 = reverse)</li>
<li><b>Position</b> &mdash; start and end coordinates in the input sequence</li>
<li><b>Length</b> &mdash; total nucleotides (including start and stop codons)</li>
<li><b>Sequence</b> &mdash; DNA sequence of the ORF</li>
<li><b>Translation</b> &mdash; predicted amino acid sequence</li>
</ul>

<h3>Example</h3>
<pre>
Input DNA:
ATGAAACCCGGGTTTAAATAG

Output:
ORF #1 | Frame: +1 | Position: 1-21 | Length: 21 nt
Sequence: ATGAAACCCGGGTTTAAATAG
Translation: MKPGFK*
</pre>

<h3>Applications</h3>
<ul>
<li>Gene prediction in prokaryotic and eukaryotic genomes</li>
<li>Coding-region (CDS) identification for annotation</li>
<li>Evaluating protein-coding potential of a genomic region</li>
<li>Finding alternative open reading frames</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Start with a larger <b>Min ORF Length</b> (300 nt) and decrease it if you miss expected ORFs</li>
<li>Use <b>Both strands</b> unless you have a specific reason to search only one</li>
<li>For eukaryotic sequences, remember that real genes may contain introns &mdash; ORF Finder works best on cDNA/mRNA sequences</li>
<li>The output is plain text; use <b>Export Result</b> to save to a file for downstream analysis</li>
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
        dialog.setWindowTitle("Help - ORF Finder")
        dialog.setFixedSize(840, 640)
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
