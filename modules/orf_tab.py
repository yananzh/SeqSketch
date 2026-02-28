from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import (
    QMessageBox, QSpinBox, QComboBox, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QWidget, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrow
import matplotlib.patches as mpatches

CODON_TABLE = {
    'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
    'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
    'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
    'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
    'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
    'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
    'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
    'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
    'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
    'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
    'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
    'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
    'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
    'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
    'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
}

class ORFTab(BaseTabWidget):
    # ── frame colours (index = frame 0-based, strand encoded in sign) ──────
    _FRAME_COLORS = {
        "+1": "#4c9be8", "+2": "#27ae60", "+3": "#e67e22",
        "-1": "#e74c3c", "-2": "#8e44ad", "-3": "#795548",
    }

    def __init__(self, parent=None):
        super().__init__("ORF Finder", "sequence")
        self._orfs: list[dict] = []
        self._seq_len: int = 0
        self._setup_drag_drop()
        self._update_ui_layout()
        self._setup_parameters()
        self._setup_gene_map()
    
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
                with open(file_path, 'r', encoding='utf-8') as f:
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
        self.chain_box.addItems(["Forward strand only", "Reverse strand only", "Both strands"])
        self.chain_box.setMinimumWidth(180)
        chain_layout.addWidget(chain_label)
        chain_layout.addWidget(self.chain_box)
        chain_layout.addStretch()
        
        # Alternative start codons
        start_codon_layout = QHBoxLayout()
        start_codon_label = QLabel("Start Codons:")
        self.start_codon_box = QComboBox()
        self.start_codon_box.addItems(["ATG only (standard)", "ATG, GTG, TTG (alternative)"])
        self.start_codon_box.setMinimumWidth(220)
        start_codon_layout.addWidget(start_codon_label)
        start_codon_layout.addWidget(self.start_codon_box)
        start_codon_layout.addStretch()
        
        self.add_content_layout(min_len_layout)
        self.add_content_layout(chain_layout)
        self.add_content_layout(start_codon_layout)

    def _setup_gene_map(self):
        """Add the linear gene map panel below the text output area."""
        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.insertWidget(self.main_layout.count() - 1, sep)

        # header row
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("<b>Linear Gene Map</b>"))
        hdr.addStretch()
        self._map_export_btn = QPushButton("Export Map (PNG)")
        self._map_export_btn.setEnabled(False)
        self._map_export_btn.clicked.connect(self._export_gene_map)
        hdr.addWidget(self._map_export_btn)
        hdr_widget = QWidget()
        hdr_widget.setLayout(hdr)
        self.main_layout.insertWidget(self.main_layout.count() - 1, hdr_widget)

        # matplotlib canvas
        self._fig = Figure(figsize=(10, 3), tight_layout=True)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setMinimumHeight(200)
        self._toolbar = NavigationToolbar(self._canvas, self)
        self.main_layout.insertWidget(self.main_layout.count() - 1, self._toolbar)
        self.main_layout.insertWidget(self.main_layout.count() - 1, self._canvas)

        # placeholder message (shown when no ORFs yet)
        self._map_placeholder = QLabel(
            "Run ORF Finder to see the linear gene map here."
        )
        self._map_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._map_placeholder.setStyleSheet("color: #aaa; font-size: 12px; padding: 20px;")
        self.main_layout.insertWidget(self.main_layout.count() - 1, self._map_placeholder)

        self._canvas.hide()
        self._toolbar.hide()

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA sequence.")
            return
        
        # Parse FASTA if present
        header = None
        if '>' in seq:
            lines = seq.split('\n')
            seq_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith('>'):
                    header = line
                elif line:
                    seq_lines.append(line)
            seq = ''.join(seq_lines)
        
        # Clean sequence
        seq = seq.replace("\n", "").replace(" ", "").upper().replace('U', 'T')
        
        if not seq:
            self.status_label.setText("No valid sequence found.")
            return
            
        if not re.fullmatch(r'[ACGTN]+', seq):
            self.status_label.setText("Invalid characters. Only A/T/G/C/N allowed.")
            return
        
        min_len = self.min_len_box.value()
        chain_mode = self.chain_box.currentIndex()
        use_alt_start = self.start_codon_box.currentIndex() == 1
        results = []
        if chain_mode in (0, 2):
            results += self.find_orfs(seq, '+', use_alt_start)
        if chain_mode in (1, 2):
            revcomp = self.reverse_complement(seq)
            results += self.find_orfs(revcomp, '-', use_alt_start)
        results = [orf for orf in results if orf['length'] >= min_len]
        if not results:
            self.output_text.setPlainText("No ORFs meet the criteria.")
            self.status_label.setText("No ORF")
            self._canvas.hide()
            self._toolbar.hide()
            self._map_placeholder.show()
            self._map_export_btn.setEnabled(False)
            return
        
        # Format output with header if present
        out = []
        if header:
            out.append(f"{header}\n")
        for idx, orf in enumerate(results, 1):
            out.append(f"ORF #{idx} | Frame: {orf['frame']} | Position: {orf['start']+1}-{orf['end']} | Length: {orf['length']} nt\nSequence: {orf['seq']}\nTranslation: {orf['aa']}\n")
        self.output_text.setPlainText('\n'.join(out))
        self.status_label.setText(f"Found {len(results)} ORFs")

        # draw gene map
        self._orfs = results
        self._seq_len = len(seq)
        self._draw_gene_map(results, len(seq))
        self._map_placeholder.hide()
        self._canvas.show()
        self._toolbar.show()
        self._map_export_btn.setEnabled(True)

    def find_orfs(self, seq, strand, use_alt_start=False):
        orfs = []
        start_codons = ['ATG', 'GTG', 'TTG'] if use_alt_start else ['ATG']
        for frame in range(3):
            i = frame
            while i < len(seq)-2:
                codon = seq[i:i+3]
                if codon in start_codons:
                    for j in range(i+3, len(seq)-2, 3):
                        stop = seq[j:j+3]
                        if stop in ('TAA', 'TAG', 'TGA'):
                            orf_seq = seq[i:j+3]
                            aa = self.translate(orf_seq)
                            orfs.append({
                                'frame': f"{strand}{frame+1}",
                                'start': i if strand=="+" else len(seq)-j-2,
                                'end': j+3 if strand=="+" else len(seq)-i,
                                'length': len(orf_seq),
                                'seq': orf_seq,
                                'aa': aa
                            })
                            i = j+3
                            break
                    else:
                        i += 3
                else:
                    i += 3
        return orfs

    def translate(self, seq):
        aa_seq = []
        for i in range(0, len(seq)-2, 3):
            codon = seq[i:i+3]
            aa = CODON_TABLE.get(codon, 'X')
            aa_seq.append(aa)
        return ''.join(aa_seq)

    def reverse_complement(self, seq):
        comp_map = str.maketrans('ACGT', 'TGCA')
        return seq.translate(comp_map)[::-1]

    # ── gene map ──────────────────────────────────────────────────────────
    def _draw_gene_map(self, orfs: list[dict], seq_len: int):
        """
        Render a SnapGene-style linear gene map.
        6 horizontal lanes (±1, ±2, ±3). Arrows point right (forward) or
        left (reverse) and are coloured by reading frame.
        """
        self._fig.clear()
        ax = self._fig.add_subplot(111)

        # lane assignment: forward +1/+2/+3 at y=2/3/4, reverse -1/-2/-3 at y=-2/-3/-4
        lane_y = {"+1": 2, "+2": 3, "+3": 4, "-1": -2, "-2": -3, "-3": -4}
        arrow_h = 0.55   # height of each arrow
        head_w  = 0.65
        margin  = seq_len * 0.015

        # draw backbone (strand labels)
        for y, label in [(1, "5' ──── Forward ────▶"), (-1, "◀──── Reverse ──── 3'")]:
            ax.axhline(y=y, xmin=0.01, xmax=0.99, color="#cccccc", lw=1.5, zorder=1)
            ax.text(
                seq_len * 0.5, y + (0.55 if y > 0 else -0.55),
                label, ha="center", va="center",
                fontsize=7, color="#aaaaaa", style="italic",
            )

        # lane axis labels
        for frame, y in lane_y.items():
            ax.text(
                -margin * 2, y, f"Frame {frame}",
                ha="right", va="center", fontsize=7.5, color="#555",
            )

        # draw each ORF as a filled arrow
        for idx, orf in enumerate(orfs, 1):
            frame = orf["frame"]
            color = self._FRAME_COLORS.get(frame, "#999999")
            y     = lane_y.get(frame, 0)
            start = orf["start"]      # 0-based
            end   = orf["end"]        # exclusive
            length = end - start

            is_fwd = frame.startswith("+")
            dx = length if is_fwd else -length
            x0 = start if is_fwd else end

            # head_length capped at 30% of orf length, minimum 3 nt
            head_len = max(3, min(length * 0.30, length - 1))

            ax.annotate(
                "", xy=(x0 + dx, y), xytext=(x0, y),
                arrowprops=dict(
                    arrowstyle=f"-|>, head_width={head_w}, head_length={head_len}",
                    color=color,
                    lw=0,
                    connectionstyle="arc3,rad=0",
                ),
                zorder=3,
            )
            # filled rectangle body (arrow shaft)
            body_x = start if is_fwd else start
            body_w = length - head_len if is_fwd else length - head_len
            if body_w > 0:
                rect_x = start if is_fwd else start + head_len
                ax.barh(
                    y, body_w, left=rect_x, height=arrow_h,
                    color=color, alpha=0.85, zorder=2, linewidth=0,
                )

            # label inside arrow (ORF#, length) if wide enough
            label_txt = f"#{idx}\n{length} nt"
            if length > seq_len * 0.04:
                mid = (start + end) / 2
                ax.text(
                    mid, y, label_txt,
                    ha="center", va="center",
                    fontsize=6.5, color="white", fontweight="bold", zorder=4,
                )

        # legend patches (only frames present in results)
        used_frames = sorted({o["frame"] for o in orfs})
        legend_patches = [
            mpatches.Patch(color=self._FRAME_COLORS[f], label=f"Frame {f}")
            for f in used_frames
        ]
        ax.legend(
            handles=legend_patches, loc="upper right",
            ncol=min(len(legend_patches), 6),
            fontsize=7.5, framealpha=0.7,
        )

        # cosmetics
        ax.set_xlim(-margin * 5, seq_len + margin)
        ax.set_ylim(-5, 5)
        ax.set_xlabel("Position (nt)", fontsize=8)
        ax.set_yticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", labelsize=7)
        ax.set_title(
            f"Linear Gene Map  —  {len(orfs)} ORF(s)  |  Sequence length: {seq_len} nt",
            fontsize=9, pad=6,
        )

        self._canvas.draw()

    def _export_gene_map(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Gene Map", "gene_map.png",
            "PNG image (*.png);;SVG (*.svg);;PDF (*.pdf);;All Files (*)",
        )
        if path:
            try:
                self._fig.savefig(path, dpi=150, bbox_inches="tight")
                QMessageBox.information(self, "Exported", f"Gene map saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
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
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
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
