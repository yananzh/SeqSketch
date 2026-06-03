from utils.common_components import (
    BaseTabWidget,
    apply_transparent_text_edit_background,
)
import re
from PyQt6.QtWidgets import (
    QMessageBox,
    QSpinBox,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
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


class ORFTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("ORF Finder", "sequence")
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
            "Paste DNA sequence in FASTA format (single sequence only) or drag-and-drop a file...\n"
            "Example:\n"
            ">seq1\n"
            "ATGAAACCCGGGTTTAAATAG"
        )
        self.output_text.setPlaceholderText("ORF results will appear here...")
        apply_transparent_text_edit_background(self.output_text)
        # Adjust minimum heights for better visibility
        self.input_text.setMinimumHeight(180)
        self.output_text.setMinimumHeight(220)

    def _setup_parameters(self):
        """Setup parameter controls with labels"""
        # Minimum length
        min_len_layout = QHBoxLayout()
        min_len_label = QLabel("Minimum ORF Length:")
        self.min_len_box = QSpinBox()
        self.min_len_box.setRange(30, 10000)
        self.min_len_box.setValue(100)
        self.min_len_box.setSuffix(" nt")
        self.min_len_box.setMinimumWidth(120)
        min_len_layout.addWidget(min_len_label)
        min_len_layout.addWidget(self.min_len_box)
        min_len_layout.addStretch()

        # Strand selection
        chain_layout = QHBoxLayout()
        chain_label = QLabel("Search Strand:")
        self.chain_box = QComboBox()
        self.chain_box.addItems([
            "Forward strand only",
            "Reverse strand only",
            "Both strands",
        ])
        self.chain_box.setCurrentIndex(2)
        self.chain_box.setMinimumWidth(180)
        chain_layout.addWidget(chain_label)
        chain_layout.addWidget(self.chain_box)
        chain_layout.addStretch()

        # Alternative start codons
        start_codon_layout = QHBoxLayout()
        start_codon_label = QLabel("Start Codons:")
        self.start_codon_box = QComboBox()
        self.start_codon_box.addItems([
            "ATG only (standard)",
            "ATG, GTG, TTG (alternative)",
        ])
        self.start_codon_box.setMinimumWidth(220)
        start_codon_layout.addWidget(start_codon_label)
        start_codon_layout.addWidget(self.start_codon_box)
        start_codon_layout.addStretch()

        self.add_content_layout(min_len_layout)
        self.add_content_layout(chain_layout)
        self.add_content_layout(start_codon_layout)

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
<h3>ORF Finder (Open Reading Frame Finder)</h3>
<p><b>Description:</b></p>
<p>Find all open reading frames (ORFs) in DNA sequences. ORFs are sequences starting with ATG (start codon) and ending with a stop codon (TAA, TAG, or TGA).</p>

<p><b>Usage:</b></p>
<ol>
<li>Paste sequence or drag-and-drop a FASTA file (single sequence only)</li>
<li>Set minimum ORF length (default: 100 nt)</li>
<li>Choose strand to search (forward, reverse, or both)</li>
<li>Click "Run" to find ORFs</li>
<li>Export or copy the ORF results</li>
</ol>

<p><b>Parameters:</b></p>
<ul>
<li><b>Minimum ORF Length:</b> Minimum nucleotide length for ORFs to report (30-10000 nt)</li>
<li><b>Search Strand:</b> Which strand(s) to analyze:
  <ul>
  <li>Forward strand only: Search +1, +2, +3 frames</li>
  <li>Reverse strand only: Search -1, -2, -3 frames (reverse complement)</li>
  <li>Both strands: Search all 6 reading frames</li>
  </ul>
</li>
<li><b>Start Codons:</b> Which codons to use as translation start:
  <ul>
  <li>ATG only (standard): Use only ATG as start codon</li>
  <li>ATG, GTG, TTG (alternative): Include alternative start codons (common in bacteria)</li>
  </ul>
</li>
</ul>

<p><b>Output information:</b></p>
<ul>
<li><b>Frame:</b> Reading frame (+1/+2/+3 for forward, -1/-2/-3 for reverse)</li>
<li><b>Position:</b> Start and end positions in the sequence</li>
<li><b>Length:</b> Length in nucleotides</li>
<li><b>Sequence:</b> DNA sequence of the ORF</li>
<li><b>Translation:</b> Amino acid sequence</li>
</ul>

<p><b>Example:</b></p>
<pre>
Input DNA:
ATGAAACCCGGGTTTAAATAG

Output:
ORF #1 | Frame: +1 | Position: 1-21 | Length: 21 nt
Sequence: ATGAAACCCGGGTTTAAATAG
Translation: MKPGFK*
</pre>

<p><b>Applications:</b></p>
<ul>
<li>Gene prediction</li>
<li>Coding region identification</li>
<li>Genome annotation</li>
<li>Protein-coding potential analysis</li>
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
        dialog.setWindowTitle("Help - ORF Finder")
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
