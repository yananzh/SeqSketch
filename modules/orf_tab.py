import os
import re

import matplotlib
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import (
    BaseTabWidget,
    validate_input_path,
    validate_output_path,
)

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

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


def reconstruct_full_header(record) -> str:
    if record.description:
        return f"{record.header} {record.description}"
    return record.header


def build_orf_report(
    input_path: str,
    full_header: str,
    results: list[dict],
    min_length: int,
    strand_label: str,
    start_codon_label: str,
) -> str:
    lines = [
        f"Input file: {input_path}",
        f"Sequence header: {full_header}",
        f"Minimum ORF length: {min_length} nt",
        f"Search strand: {strand_label}",
        f"Start codons: {start_codon_label}",
        f"Total ORFs: {len(results)}",
        "",
    ]

    if not results:
        lines.append("No ORFs meet the selected criteria.")
        return "\n".join(lines)

    for idx, orf in enumerate(results, 1):
        lines.extend([
            f"ORF #{idx} | Frame: {orf['frame']} | Position: {orf['start'] + 1}-{orf['end']} | Length: {orf['length']} nt",
            f"Sequence: {orf['seq']}",
            f"Translation: {orf['aa']}",
            "",
        ])
    return "\n".join(lines).rstrip()


class FileDropLineEdit(QLineEdit):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls:
                local = urls[0].toLocalFile()
                if self._is_valid_fasta(local):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            local = urls[0].toLocalFile()
            if self._is_valid_fasta(local):
                self.setText(local)
                self.file_dropped.emit(local)
                event.acceptProposedAction()
                return
        event.ignore()

    @staticmethod
    def _is_valid_fasta(path: str) -> bool:
        allowed = {".fasta", ".fa", ".fas", ".fna", ".ffn", ".txt"}
        try:
            ext = os.path.splitext(path)[1].lower()
            return os.path.isfile(path) and ext in allowed
        except Exception:
            return False


class ORFTab(BaseTabWidget):
    _FRAME_COLORS = {
        "+1": "#4c9be8",
        "+2": "#27ae60",
        "+3": "#e67e22",
        "-1": "#e74c3c",
        "-2": "#8e44ad",
        "-3": "#795548",
    }

    def __init__(self, parent=None):
        super().__init__("ORF Finder", "file")
        self._orfs: list[dict] = []
        self._seq_len = 0
        self._full_header = ""
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input FASTA file:"))
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText(
            "Select or drop a single-sequence FASTA file..."
        )
        self.input_edit.setMinimumWidth(320)
        self.input_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.setSpacing(8)

        self.input_hint = QLabel(
            "Single sequence only. Select one DNA FASTA file; the ORF report will be written to the output file and previewed below."
        )
        self.input_hint.setWordWrap(True)
        self.input_hint.setStyleSheet("color: #666; font-size: 10pt;")

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output report file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the ORF report...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)

        min_len_layout = QHBoxLayout()
        min_len_layout.addWidget(QLabel("Minimum ORF Length:"))
        self.min_len_box = QSpinBox()
        self.min_len_box.setRange(3, 10000)
        self.min_len_box.setValue(100)
        self.min_len_box.setSuffix(" nt")
        self.min_len_box.setMinimumWidth(120)
        min_len_layout.addWidget(self.min_len_box)
        min_len_layout.addStretch()

        chain_layout = QHBoxLayout()
        chain_layout.addWidget(QLabel("Search Strand:"))
        self.chain_box = QComboBox()
        self.chain_box.addItems([
            "Forward strand only",
            "Reverse strand only",
            "Both strands",
        ])
        self.chain_box.setCurrentText("Both strands")
        self.chain_box.setMinimumWidth(180)
        chain_layout.addWidget(self.chain_box)
        chain_layout.addStretch()

        start_codon_layout = QHBoxLayout()
        start_codon_layout.addWidget(QLabel("Start Codons:"))
        self.start_codon_box = QComboBox()
        self.start_codon_box.addItems([
            "ATG only (standard)",
            "ATG, GTG, TTG (alternative)",
        ])
        self.start_codon_box.setMinimumWidth(220)
        start_codon_layout.addWidget(self.start_codon_box)
        start_codon_layout.addStretch()

        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        preview_label = QLabel("ORF Report Preview:")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText(
            "Run ORF Finder to preview the saved report here..."
        )
        self.preview_text.setMinimumHeight(220)

        self.add_content_layout(input_layout)
        self.add_content_widget(self.input_hint)
        self.add_content_layout(output_layout)
        self.add_content_layout(min_len_layout)
        self.add_content_layout(chain_layout)
        self.add_content_layout(start_codon_layout)
        self.add_content_layout(control_layout)
        self.add_content_widget(preview_label)
        self.add_content_widget(self.preview_text)
        self._setup_gene_map()
        self.content_area.addStretch()

    def _setup_gene_map(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.add_content_widget(sep)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("<b>ORF Map</b>"))
        hdr.addStretch()
        self._map_export_btn = QPushButton("Export Map")
        self._map_export_btn.setEnabled(False)
        self._map_export_btn.clicked.connect(self._export_gene_map)
        hdr.addWidget(self._map_export_btn)
        hdr_widget = QWidget()
        hdr_widget.setLayout(hdr)
        self.add_content_widget(hdr_widget)

        self._fig = Figure(figsize=(10, 3), tight_layout=True)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setMinimumHeight(220)
        self._toolbar = NavigationToolbar(self._canvas, self)
        self.add_content_widget(self._toolbar)
        self.add_content_widget(self._canvas)

        self._map_placeholder = QLabel(
            "Run ORF Finder to see the directional ORF map here."
        )
        self._map_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._map_placeholder.setStyleSheet(
            "color: #aaa; font-size: 12px; padding: 20px;"
        )
        self.add_content_widget(self._map_placeholder)

        self._canvas.hide()
        self._toolbar.hide()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_orf_finder)
        self.clear_btn.clicked.connect(self.clear_all)
        self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FASTA file",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.txt);;All Files (*)",
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_orf_report.txt")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ORF report",
            "",
            "Text Files (*.txt);;TSV Files (*.tsv);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.preview_text.clear()
        self.log_area.clear()
        self.min_len_box.setValue(100)
        self.chain_box.setCurrentText("Both strands")
        self.start_codon_box.setCurrentIndex(0)
        self._orfs = []
        self._seq_len = 0
        self._full_header = ""
        self._canvas.hide()
        self._toolbar.hide()
        self._map_placeholder.show()
        self._map_export_btn.setEnabled(False)
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        if running:
            self.show_status("Processing...")
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.input_edit.setEnabled(not running)
        self.output_edit.setEnabled(not running)
        self.min_len_box.setEnabled(not running)
        self.chain_box.setEnabled(not running)
        self.start_codon_box.setEnabled(not running)
        self._map_export_btn.setEnabled(not running and bool(self._orfs))

    def run(self):
        self.run_orf_finder()

    def run_orf_finder(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".txt"],
        )
        if not valid:
            self.log_message(error, "ERROR")
            return

        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return

        self.set_running_state(True)
        try:
            record = self._load_single_sequence(input_path)
            if record is None:
                return

            seq = record.sequence.replace("U", "T")
            if not re.fullmatch(r"[ACGTN]+", seq):
                self.log_message(
                    "Invalid characters found in sequence. Only A/T/G/C/N are supported.",
                    "ERROR",
                )
                return

            min_len = self.min_len_box.value()
            chain_mode = self.chain_box.currentIndex()
            use_alt_start = self.start_codon_box.currentIndex() == 1

            results = []
            if chain_mode in (0, 2):
                results.extend(self.find_orfs(seq, "+", use_alt_start))
            if chain_mode in (1, 2):
                revcomp = self.reverse_complement(seq)
                results.extend(self.find_orfs(revcomp, "-", use_alt_start))

            results = [orf for orf in results if orf["length"] >= min_len]
            results.sort(key=lambda item: (item["start"], item["frame"]))
            self._orfs = results
            self._seq_len = len(seq)
            self._full_header = reconstruct_full_header(record)

            report_text = build_orf_report(
                input_path,
                self._full_header,
                results,
                min_len,
                self.chain_box.currentText(),
                self.start_codon_box.currentText(),
            )

            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(report_text)

            self.preview_text.setPlainText(report_text)

            if results:
                self._draw_gene_map(results, len(seq))
                self._map_placeholder.hide()
                self._canvas.show()
                self._toolbar.show()
                self._map_export_btn.setEnabled(True)
                self.log_message(
                    f"Found {len(results)} ORF(s). Report saved to: {output_path}",
                    "INFO",
                )
                self.show_status(f"Found {len(results)} ORFs")
            else:
                self._canvas.hide()
                self._toolbar.hide()
                self._map_placeholder.show()
                self._map_export_btn.setEnabled(False)
                self.log_message(
                    f"No ORFs met the criteria. Report saved to: {output_path}",
                    "WARNING",
                )
                self.show_status("No ORF")
        except Exception as exc:
            self.log_message(f"Error during ORF search: {exc}", "ERROR")
        finally:
            self.set_running_state(False)

    def _load_single_sequence(self, input_path: str):
        from modules.fasta_processor import FASTAProcessor

        processor = FASTAProcessor()
        self.log_message("Loading FASTA file...", "INFO")
        if not processor.read_file(input_path):
            self.log_message("Failed to read FASTA file", "ERROR")
            return None
        if not processor.records:
            self.log_message("No sequences found in FASTA file", "ERROR")
            return None
        if len(processor.records) != 1:
            self.log_message(
                "ORF Finder currently supports single-sequence FASTA files only",
                "ERROR",
            )
            return None
        return processor.records[0]

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
        for index in range(0, len(seq) - 2, 3):
            codon = seq[index : index + 3]
            aa = CODON_TABLE.get(codon, "X")
            aa_seq.append(aa)
        return "".join(aa_seq)

    def reverse_complement(self, seq):
        comp_map = str.maketrans("ACGT", "TGCA")
        return seq.translate(comp_map)[::-1]

    def _draw_gene_map(self, orfs: list[dict], seq_len: int):
        self._fig.clear()
        ax = self._fig.add_subplot(111)

        lane_y = {"+1": 2, "+2": 3, "+3": 4, "-1": -2, "-2": -3, "-3": -4}
        arrow_h = 0.55
        head_w = 0.65
        margin = seq_len * 0.015

        for y, label in [(1, "5' ──── Forward ────▶"), (-1, "◀──── Reverse ──── 3'")]:
            ax.axhline(y=y, xmin=0.01, xmax=0.99, color="#cccccc", lw=1.5, zorder=1)
            ax.text(
                seq_len * 0.5,
                y + (0.55 if y > 0 else -0.55),
                label,
                ha="center",
                va="center",
                fontsize=7,
                color="#aaaaaa",
                style="italic",
            )

        for frame, y in lane_y.items():
            ax.text(
                -margin * 2,
                y,
                f"Frame {frame}",
                ha="right",
                va="center",
                fontsize=7.5,
                color="#555",
            )

        for idx, orf in enumerate(orfs, 1):
            frame = orf["frame"]
            color = self._FRAME_COLORS.get(frame, "#999999")
            y = lane_y.get(frame, 0)
            start = orf["start"]
            end = orf["end"]
            length = end - start

            is_forward = frame.startswith("+")
            dx = length if is_forward else -length
            x0 = start if is_forward else end
            head_len = max(3, min(length * 0.30, length - 1))

            ax.annotate(
                "",
                xy=(x0 + dx, y),
                xytext=(x0, y),
                arrowprops=dict(
                    arrowstyle=f"-|>, head_width={head_w}, head_length={head_len}",
                    color=color,
                    lw=0,
                    connectionstyle="arc3,rad=0",
                ),
                zorder=3,
            )

            body_w = length - head_len
            if body_w > 0:
                rect_x = start if is_forward else start + head_len
                ax.barh(
                    y,
                    body_w,
                    left=rect_x,
                    height=arrow_h,
                    color=color,
                    alpha=0.85,
                    zorder=2,
                    linewidth=0,
                )

            label_txt = f"#{idx}\n{length} nt"
            if length > seq_len * 0.04:
                mid = (start + end) / 2
                ax.text(
                    mid,
                    y,
                    label_txt,
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="white",
                    fontweight="bold",
                    zorder=4,
                )

        used_frames = sorted({orf["frame"] for orf in orfs})
        legend_patches = [
            mpatches.Patch(color=self._FRAME_COLORS[frame], label=f"Frame {frame}")
            for frame in used_frames
        ]
        if legend_patches:
            ax.legend(
                handles=legend_patches,
                loc="upper right",
                ncol=min(len(legend_patches), 6),
                fontsize=7.5,
                framealpha=0.7,
            )

        ax.set_xlim(-margin * 5, seq_len + margin)
        ax.set_ylim(-5, 5)
        ax.set_xlabel("Position (nt)", fontsize=8)
        ax.set_yticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", labelsize=7)
        ax.set_title(
            f"Directional ORF Map  |  {len(orfs)} ORF(s)  |  Sequence length: {seq_len} nt",
            fontsize=9,
            pad=6,
        )

        self._canvas.draw()

    def save_gene_map(self, path: str) -> bool:
        if not path or not self._orfs:
            return False
        try:
            self._fig.savefig(path, dpi=150, bbox_inches="tight")
            return True
        except Exception as exc:
            self.log_message(f"Failed to save gene map: {exc}", "ERROR")
            return False

    def _export_gene_map(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ORF map",
            "orf_map.png",
            "PNG image (*.png);;PDF document (*.pdf);;All Files (*)",
        )
        if not path:
            return
        if self.save_gene_map(path):
            self.log_message(f"Gene map saved to: {path}", "INFO")
            self.show_status(f"Map saved: {path}")

    def show_help(self):
        help_text = """
<h3>ORF Finder</h3>
<p><b>Description:</b></p>
<p>Scan a single FASTA sequence file for open reading frames and export the result as a report file. The ORF map uses arrows to show gene direction and genomic position across the forward and reverse frames.</p>

<p><b>Workflow:</b></p>
<ol>
<li>Select a single-sequence FASTA file</li>
<li>Choose the output report path</li>
<li>Set minimum ORF length, search strand, and allowed start codons</li>
<li>Click <b>Start</b> to generate the report and ORF map</li>
<li>Export the ORF map as <b>PNG</b> or <b>PDF</b> if needed</li>
</ol>

<p><b>Search Strand options:</b></p>
<ul>
<li><b>Forward strand only:</b> search +1, +2, +3 frames</li>
<li><b>Reverse strand only:</b> search -1, -2, -3 frames</li>
<li><b>Both strands:</b> search all 6 reading frames (default)</li>
</ul>

<p><b>Example input:</b></p>
<pre>
>seq1
ATGAAACCCGGGTTTAAATAG
</pre>

<p><b>Example report excerpt:</b></p>
<pre>
ORF #1 | Frame: +1 | Position: 1-21 | Length: 21 nt
Sequence: ATGAAACCCGGGTTTAAATAG
Translation: MKPGFK*
</pre>

<p><b>Notes:</b></p>
<ul>
<li>Current workflow accepts one FASTA record per run.</li>
<li>RNA input is converted internally to DNA by replacing U with T.</li>
<li>The map arrows indicate the direction and span of each predicted ORF.</li>
</ul>
        """
        from PyQt6.QtWidgets import QDialog, QScrollArea

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - ORF Finder")
        dialog.setFixedSize(840, 600)
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
