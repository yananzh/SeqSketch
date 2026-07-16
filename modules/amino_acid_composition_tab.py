from PyQt6.QtWidgets import QMessageBox, QFileDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget, apply_transparent_text_edit_background
from utils.example_data import load_example_text
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import re
import csv

AMINO_ACIDS = [
    "A",
    "R",
    "N",
    "D",
    "C",
    "Q",
    "E",
    "G",
    "H",
    "I",
    "L",
    "K",
    "M",
    "F",
    "P",
    "S",
    "T",
    "W",
    "Y",
    "V",
]


class AminoAcidCompositionTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Amino Acid Composition", "sequence")
        # Customize buttons/text
        self.run_btn.setText("Analyze")
        # Hide copy button per requirement
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()
        # Hide default export button — we add our own in the status row
        if hasattr(self, "export_btn"):
            self.export_btn.hide()
        # Add Export CSV button to status row after Analyze
        self.export_csv_btn = QPushButton(self.tr("Export CSV"))
        self.export_csv_btn.setFixedWidth(110)
        self.export_csv_btn.clicked.connect(self.export_csv)
        _idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(_idx + 1, self.export_csv_btn)
        # storage for current results
        self.current_results = []
        # Update placeholders for protein sequences
        self.input_text.setPlaceholderText(
            "Paste protein sequence(s) in FASTA format or drag-and-drop a file...\n"
            "Examples:\n>prot1\nMKTFFVAGLMAGIS\n>prot2\nMVLSEGEWQLVLHVWAKVEADVAGHGQDIL"
        )
        self.output_text.setPlaceholderText(
            "Amino acid composition (counts and percentages) will appear here..."
        )
        apply_transparent_text_edit_background(self.output_text)
        _s = self.output_text.styleSheet()
        _s = _s.replace("border: 1px solid #94a3b8;", "border: none;")
        self.output_text.setStyleSheet(_s)
        # Enable drag-and-drop
        self._setup_drag_drop()

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
        """Load the bundled protein example."""
        text = load_example_text("protein", "protein_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("Loaded example data: protein_example.fasta"))

    def run(self):
        self.status_label.setText("")
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, "Input Error", "Please input or load FASTA protein sequences."
            )
            return
        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "Format Error", str(e))
            return
        if not records:
            QMessageBox.warning(self, "Input Error", "No valid FASTA sequences detected.")
            return
        output_lines = []
        self.current_results = []
        for header, seq in records:
            seq = seq.upper()
            if not all(c in AMINO_ACIDS for c in seq):
                QMessageBox.warning(
                    self,
                    "Sequence Error",
                    f"Sequence {header} contains non-standard amino acids.",
                )
                return
            analysis = ProteinAnalysis(seq)
            freq = analysis.get_amino_acids_percent()  # fraction per amino acid
            total_len = len(seq)
            output_lines.append(f">{header} | Length: {total_len} aa")
            # Column header
            output_lines.append("AA  Count  Percent")
            for aa in AMINO_ACIDS:
                count = seq.count(aa)
                percent = freq.get(aa, 0) * 100
                output_lines.append(f"{aa:<2}  {count:<5}  {percent:>6.2f}%")
            # store structured result for CSV export
            self.current_results.append({
                "header": header,
                "length": total_len,
                "counts": {aa: seq.count(aa) for aa in AMINO_ACIDS},
                "percents": {aa: freq.get(aa, 0) * 100 for aa in AMINO_ACIDS},
            })
            output_lines.append("")
        self.output_text.setPlainText("\n".join(output_lines))
        self.status_label.setText(f"Analyzed {len(records)} sequences.")

    def _setup_drag_drop(self):
        self.input_text.setAcceptDrops(True)
        self.input_text.dragEnterEvent = self._drag_enter_event
        self.input_text.dropEvent = self._drop_event

    def _drag_enter_event(self, event):
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"Loaded file: {file_path}")
                event.acceptProposedAction()
            except Exception as e:
                self.status_label.setText(f"Error loading file: {e}")
                event.ignore()

    def parse_fasta(self, text):
        records = []
        header = None
        seq_lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header and seq_lines:
                    records.append((header, "".join(seq_lines)))
                header = line[1:].strip()
                seq_lines = []
            else:
                if not re.match(r"^[A-Za-z]+$", line):
                    raise ValueError(f"Sequence line contains invalid characters: {line}")
                seq_lines.append(line)
        if header and seq_lines:
            records.append((header, "".join(seq_lines)))
        return records

    def show_help(self):
        help_text = self.tr(
            "<h2>Amino Acid Composition &mdash; Protein AA Profiling</h2>"
            "<p><b>What does this tool do?</b><br>"
            "It computes the count and percentage of each of the 20 standard amino acids "
            "in one or more protein sequences. Results are shown per sequence and can be "
            "exported as a CSV spreadsheet.</p>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Paste one or more protein sequences in FASTA format</li>"
            "<li>Click <b>Analyze</b></li>"
            "<li>Review the per-sequence amino acid counts and percentages</li>"
            "<li>Click <b>Export CSV</b> to save a spreadsheet for further analysis</li>"
            "</ol>"
            "<h3>Input Format</h3>"
            "<ul>"
            "<li>FASTA format: <code>&gt;header</code> followed by the protein sequence</li>"
            "<li>Only the 20 standard amino acids are recognised: "
            "<code>A R N D C Q E G H I L K M F P S T W Y V</code></li>"
            "<li>Non-standard characters trigger a warning; sequences are still processed</li>"
            "</ul>"
            "<h3>Output</h3>"
            "<ul>"
            "<li>Per sequence: header, length, and a table of each AA with count and percentage</li>"
            "<li>Percentages are based on total sequence length (two decimal places)</li>"
            "</ul>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Multi-FASTA input is supported &mdash; each sequence is analysed independently</li>"
            "<li>Use <b>Export CSV</b> to open the composition table in Excel or R</li>"
            "</ul>"
        )
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )
        from PyQt6.QtCore import Qt as QtCore

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Help - Amino Acid Composition"))
        dlg.setFixedSize(780, 560)
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.AlignmentFlag.AlignTop | QtCore.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll.setWidget(label)
        layout.addWidget(scroll)
        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_box.addWidget(ok)
        layout.addLayout(btn_box)
        dlg.setLayout(layout)
        dlg.exec()

    def export_csv(self):
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please run analysis first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Amino Acid Composition CSV",
            "amino_acid_composition.csv",
            "CSV Files (*.csv)",
        )
        if not file_path:
            return
        # Prepare header: header,length, then per AA count and percent
        header_cols = ["Sequence_ID", "Length"]
        for aa in AMINO_ACIDS:
            header_cols.append(f"{aa}_count")
            header_cols.append(f"{aa}_percent")
        try:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header_cols)
                for rec in self.current_results:
                    row = [rec["header"], rec["length"]]
                    for aa in AMINO_ACIDS:
                        row.append(rec["counts"][aa])
                        row.append(f"{rec['percents'][aa]:.2f}")
                    writer.writerow(row)
            self.status_label.setText(f"Exported CSV: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
