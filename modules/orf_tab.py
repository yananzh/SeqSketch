from utils.common_components import BaseTabWidget
from utils.example_data import load_example_text
import re
from PyQt6.QtWidgets import (
    QSpinBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QAbstractItemView,
    QWidget,
    QPushButton,
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

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
            "Paste DNA sequence in FASTA format "
            "or drag-and-drop a file...\n"
            "Example:\n"
            ">seq1\n"
            "ATGAAACCCGGGTTTAAATAG"
        )
        self.output_text.setPlaceholderText("ORF results will appear here...")
        self.input_text.setMinimumHeight(100)
        self._build_results_area()
        self._results: list = []

        # Add export button between Run and Clear in the status row
        self.export_orf_btn = QPushButton(self.tr("Export ORFs"))
        self.export_orf_btn.setFixedWidth(110)
        self.export_orf_btn.clicked.connect(self.export_result)
        idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(idx + 1, self.export_orf_btn)

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
        """Load the bundled lambda phage DNA example for ORF finding."""
        text = load_example_text("dna", "lambda_1kb.fasta")
        if not text:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("已载入示例数据: lambda_1kb.fasta"))

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

    def _build_results_area(self):
        """Build the QTableWidget + Matplotlib ORF map below parameters."""
        # Insert results QGroupBox before the output group
        grp_results = QGroupBox(self.tr("ORF Results"))
        grp_results.setFlat(True)
        gr_layout = QVBoxLayout(grp_results)
        gr_layout.setContentsMargins(0, 16, 0, 4)
        gr_layout.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── ORF table ──────────────────────────────────────────────
        self._orf_table = QTableWidget(0, 6)
        self._orf_table.setHorizontalHeaderLabels([
            "#",
            "Frame",
            "Start",
            "End",
            "Length (nt)",
            "Length (aa)",
        ])
        self._orf_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self._orf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._orf_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._orf_table.setAlternatingRowColors(True)
        self._orf_table.setMinimumWidth(420)
        splitter.addWidget(self._orf_table)

        # ── ORF map (Matplotlib) ───────────────────────────────────
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(2)

        self._orf_fig = Figure(figsize=(6, 3), dpi=100)
        self._orf_canvas = FigureCanvas(self._orf_fig)
        self._orf_canvas.setMinimumHeight(160)
        self._orf_toolbar = NavigationToolbar(self._orf_canvas, map_container)
        map_layout.addWidget(self._orf_toolbar)
        map_layout.addWidget(self._orf_canvas)
        splitter.addWidget(map_container)

        splitter.setSizes([500, 400])
        gr_layout.addWidget(splitter)
        self.add_content_widget(grp_results)

        # Hide the BaseTabWidget output group — we use the table instead
        self.output_group.setVisible(False)

    # ── Core algorithm ─────────────────────────────────────────────────

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText("Please enter a DNA sequence.")
            return

        # Parse FASTA records (support single raw sequence and multi-FASTA)
        header = None
        records: list[tuple[str, str]] = []  # (header_or_label, clean_seq)
        if ">" in raw:
            lines = raw.split("\n")
            seq_lines: list[str] = []
            current_header = None
            for line in lines:
                line = line.strip()
                if line.startswith(">"):
                    if current_header is not None and seq_lines:
                        seq = "".join(seq_lines)
                        records.append((current_header, seq))
                        seq_lines = []
                    current_header = line
                elif line:
                    seq_lines.append(line)
            if current_header is not None and seq_lines:
                records.append((current_header, "".join(seq_lines)))
        else:
            records = [("Single sequence", raw)]

        min_len = self.min_len_box.value()
        chain_mode = self.chain_box.currentIndex()
        use_alt_start = self.start_codon_box.currentIndex() == 1

        all_results: list[dict] = []
        for record_idx, (rec_header, seq) in enumerate(records):
            seq = seq.replace(" ", "").upper().replace("U", "T")
            if not seq:
                continue
            if not re.fullmatch(r"[ACGTN]+", seq):
                self.status_label.setText(
                    f"Invalid characters in record \"{rec_header}\". "
                    "Only A/T/G/C/N allowed."
                )
                return

            # Tag with origin header so multi-record output is readable
            prefix = f" [{rec_header}]" if len(records) > 1 else ""
            results = []
            if chain_mode in (0, 2):
                results += self.find_orfs(seq, "+", use_alt_start)
            if chain_mode in (1, 2):
                revcomp = self.reverse_complement(seq)
                results += self.find_orfs(
                    revcomp, "-", use_alt_start, original_len=len(seq)
                )
            for o in results:
                o["header_tag"] = prefix
            results = [o for o in results if o["length"] >= min_len]
            all_results.extend(results)

        all_results.sort(key=lambda o: o["length"], reverse=True)

        self._results = all_results
        self._populate_table(all_results)
        if records:
            self._draw_orf_map(all_results, len(records[0][1]))

        # Also populate output_text for export/copy
        out_lines = []
        for idx, o in enumerate(all_results, 1):
            start_disp = o["start"]
            end_disp = o["end"]
            if o["frame"].startswith("-") and start_disp < end_disp:
                start_disp, end_disp = end_disp, start_disp
            tag = o.get("header_tag", "")
            out_lines.append(
                f"ORF #{idx}{tag} | Frame: {o['frame']} | "
                f"Position: {start_disp}-{end_disp} | Length: {o['length']} nt\n"
                f"Sequence: {o['seq']}\nTranslation: {o['aa']}\n"
            )
        self.output_text.setPlainText("\n".join(out_lines))
        self.status_label.setText(f"Found {len(all_results)} ORFs  (sorted by length)")

    def find_orfs(self, seq, strand, use_alt_start=False, original_len=None):
        """Find ORFs.  *seq* is already reverse-complemented for the '-' strand."""
        orfs = []
        start_codons = ["ATG", "GTG", "TTG"] if use_alt_start else ["ATG"]
        n = len(seq)
        for frame in range(3):
            i = frame
            while i < n - 2:
                codon = seq[i : i + 3]
                if codon in start_codons:
                    for j in range(i + 3, n - 2, 3):
                        stop = seq[j : j + 3]
                        if stop in ("TAA", "TAG", "TGA"):
                            orf_seq = seq[i : j + 3]
                            aa = self.translate(orf_seq)
                            if strand == "+":
                                s, e = i + 1, j + 3  # 1‑based, forward
                            else:
                                # RC at [i, j+2] → original coords (N - j - 2, N - i)
                                s = n - i  # 5' end (higher coord)
                                e = n - j - 2  # 3' end (lower coord)
                            orfs.append({
                                "frame": f"{strand}{frame + 1}",
                                "start": s,
                                "end": e,
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

    @staticmethod
    def translate(seq):
        aa_seq = []
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            aa = CODON_TABLE.get(codon, "X")
            aa_seq.append(aa)
        return "".join(aa_seq)

    @staticmethod
    def reverse_complement(seq):
        comp_map = str.maketrans("ACGT", "TGCA")
        return seq.translate(comp_map)[::-1]

    # ── Table population ───────────────────────────────────────────────

    def _populate_table(self, results):
        self._orf_table.setRowCount(len(results))
        for row, o in enumerate(results):
            start_disp = o["start"]
            end_disp = o["end"]
            if o["frame"].startswith("-") and start_disp < end_disp:
                start_disp, end_disp = end_disp, start_disp
            items = [
                QTableWidgetItem(str(row + 1)),
                QTableWidgetItem(o["frame"]),
                QTableWidgetItem(str(start_disp)),
                QTableWidgetItem(str(end_disp)),
                QTableWidgetItem(str(o["length"])),
                QTableWidgetItem(str(len(o["aa"]))),
            ]
            for ci in (0, 2, 3, 4, 5):
                items[ci].setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
            for ci, item in enumerate(items):
                self._orf_table.setItem(row, ci, item)

    # ── ORF map ────────────────────────────────────────────────────────

    def _draw_orf_map(self, results, seq_len):
        self._orf_fig.clear()

        frames = ["+1", "+2", "+3", "-1", "-2", "-3"]
        colors = [
            "#1976d2",
            "#388e3c",
            "#f57c00",
            "#d32f2f",
            "#7b1fa2",
            "#00796b",
        ]

        ax = self._orf_fig.add_subplot(111)
        ax.set_facecolor("#fafafa")
        bar_h = 0.55

        for track_idx, fname in enumerate(frames):
            y_base = 5.5 - track_idx
            ax.plot(
                [1, seq_len],
                [y_base, y_base],
                color="#ddd",
                linewidth=0.6,
                zorder=0,
            )
            frame_orfs = [o for o in results if o["frame"] == fname]
            for o in frame_orfs:
                s, e = o["start"], o["end"]
                if s > e:
                    s, e = e, s
                w = e - s + 1
                color = colors[track_idx]
                ax.broken_barh(
                    [(s, w)],
                    (y_base - bar_h / 2, bar_h),
                    facecolors=color,
                    edgecolors="none",
                    alpha=0.7,
                    zorder=2,
                )
                # Arrowhead
                if fname.startswith("+"):
                    ax.plot(e, y_base, marker=">", color=color, markersize=5, zorder=3)
                else:
                    ax.plot(s, y_base, marker="<", color=color, markersize=5, zorder=3)

            ax.text(
                -seq_len * 0.01,
                y_base,
                fname,
                ha="right",
                va="center",
                fontsize=7,
                color=colors[track_idx],
                fontweight="bold",
            )

        ax.set_xlim(-seq_len * 0.06, seq_len * 1.02)
        ax.set_ylim(-0.2, 6.2)
        ax.set_yticks([])
        ax.set_xlabel("Sequence position (bp)", fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        self._orf_fig.tight_layout(pad=0.5)
        self._orf_canvas.draw_idle()

    # ── Override export / copy to use FASTA output ─────────────────────

    def export_result(self):
        """Export ORF sequences as FASTA, sorted by length descending."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        if not self._results:
            QMessageBox.information(self, "No Results", "Run the ORF finder first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ORFs",
            "orfs.fasta",
            "FASTA Files (*.fasta);;Text Files (*.txt)",
        )
        if path:
            sorted_results = sorted(
                self._results, key=lambda o: o["length"], reverse=True
            )
            with open(path, "w", encoding="utf-8") as fh:
                for idx, o in enumerate(sorted_results, 1):
                    fh.write(
                        f">ORF_{idx} | Frame:{o['frame']} | "
                        f"Pos:{o['start']}-{o['end']} | "
                        f"Len:{o['length']}nt\n{o['seq']}\n"
                    )
            self.status_label.setText(f"Exported {len(sorted_results)} ORFs to {path}")

    def copy_result(self):
        """Copy selected ORF sequences to clipboard."""
        from PyQt6.QtWidgets import QApplication

        rows = set()
        for idx in self._orf_table.selectionModel().selectedRows():
            rows.add(idx.row())
        if not rows:
            # Fallback: copy all
            if not self._results:
                return
            QApplication.clipboard().setText("\n".join(o["aa"] for o in self._results))
            self.status_label.setText("Copied all ORFs to clipboard")
            return
        selected = [self._results[r] for r in sorted(rows)]
        QApplication.clipboard().setText("\n".join(o["aa"] for o in selected))
        self.status_label.setText(f"Copied {len(selected)} ORF(s) to clipboard")

    # ── Help ───────────────────────────────────────────────────────────

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
<li>The output is shown in a sortable table &mdash; click column headers to sort by length, frame, or position.  Use <b>Copy to Clipboard</b> to copy selected ORF sequences, or <b>Export Result</b> to save all ORFs as a FASTA file.</li>
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
