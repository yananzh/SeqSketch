import csv
import os
import re

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from utils.common_components import BaseTabWidget, unify_status_button_sizes
from utils.example_data import load_example_text

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


class _NumItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically instead of lexicographically."""

    def __init__(self, value: float, text: str):
        super().__init__(text)
        self._val = value

    def __lt__(self, other):
        try:
            return self._val < other._val
        except Exception:
            return super().__lt__(other)


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
        self.export_csv_btn.setProperty("accentButton", True)
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self.export_csv)
        self.export_csv_btn.style().unpolish(self.export_csv_btn)
        self.export_csv_btn.style().polish(self.export_csv_btn)
        _idx = self.status_layout.indexOf(self.run_btn)
        self.status_layout.insertWidget(_idx + 1, self.export_csv_btn)
        # Add Result Folder button after Export CSV
        self.open_folder_btn = QPushButton(self.tr("Result Folder"))
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.style().unpolish(self.open_folder_btn)
        self.open_folder_btn.style().polish(self.open_folder_btn)
        self.status_layout.insertWidget(_idx + 2, self.open_folder_btn)
        self._last_export_dir = ""
        # storage for current results
        self.current_results = []
        # Update placeholders for protein sequences
        self.input_text.setPlaceholderText(
            "Paste protein sequence(s) in FASTA format or drag-and-drop a file...\n"
            "Examples:\n>prot1\nMKTFFVAGLMAGIS\n>prot2\nMVLSEGEWQLVLHVWAKVEADVAGHGQDIL"
        )
        self.input_hint.hide()
        # Results are shown in per-sequence tables
        self._setup_results_area()
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
        unify_status_button_sizes(self)

    def _setup_results_area(self):
        """Replace the plain-text output with one long-format AA table."""
        og_layout = self.output_group.layout()
        og_layout.removeWidget(self.output_text)
        self.output_text.hide()

        self._aa_table = QTableWidget(0, 4)
        self._aa_table.setHorizontalHeaderLabels(["Sequence ID", "AA", "Count", "Percent"])
        header = self._aa_table.horizontalHeader()
        header.setMinimumSectionSize(70)
        for col in range(4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._aa_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._aa_table.setSortingEnabled(True)
        self._aa_table.setMinimumHeight(200)
        og_layout.insertWidget(0, self._aa_table)

    @staticmethod
    def _short_header(header: str) -> str:
        """Short tab title for a FASTA record (first token, max 20 chars)."""
        name = header.split()[0].strip() if header.strip() else ""
        name = name or "sequence"
        return name if len(name) <= 20 else name[:17] + "..."

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
        self._aa_table.setSortingEnabled(False)
        self._aa_table.setRowCount(len(records) * len(AMINO_ACIDS))
        self.current_results = []
        row_idx = 0
        for header, seq in records:
            seq = seq.upper()
            if not all(c in AMINO_ACIDS for c in seq):
                QMessageBox.warning(
                    self,
                    "Sequence Error",
                    f"Sequence {header} contains non-standard amino acids.",
                )
                return
            total_len = len(seq)
            counts = {aa: seq.count(aa) for aa in AMINO_ACIDS}
            # Percent is computed directly (count / length * 100); Biopython's
            # amino_acids_percent reports per-1000 frequencies, not percents.
            percents = {aa: counts[aa] / total_len * 100 for aa in AMINO_ACIDS}
            # store structured result for CSV export
            self.current_results.append({
                "header": header,
                "length": total_len,
                "counts": counts,
                "percents": percents,
            })
            seq_id = self._short_header(header)
            for aa in AMINO_ACIDS:
                self._aa_table.setItem(row_idx, 0, QTableWidgetItem(seq_id))
                self._aa_table.setItem(row_idx, 1, QTableWidgetItem(aa))
                self._aa_table.setItem(row_idx, 2, _NumItem(float(counts[aa]), str(counts[aa])))
                self._aa_table.setItem(row_idx, 3, _NumItem(percents[aa], f"{percents[aa]:.2f}"))
                row_idx += 1
        self._aa_table.setSortingEnabled(True)
        self.export_csv_btn.setEnabled(True)
        self.status_label.setText(f"Analyzed {len(records)} sequences.")

    def clear(self):
        self._aa_table.setRowCount(0)
        self.current_results = []
        self.export_csv_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(False)
        super().clear()

    def _open_output_folder(self):
        """Open the folder of the most recently exported CSV file."""
        if self._last_export_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

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
            "<li>Non-standard characters trigger a warning and processing stops &mdash; remove residues like X, U, B, Z and re-run</li>"
            "</ul>"
            "<h3>Output</h3>"
            "<ul>"
            "<li>Per sequence: a table of each amino acid with count and percentage</li>"
            "<li>Percentages are based on total sequence length (two decimal places)</li>"
            "</ul>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Multi-FASTA input is supported &mdash; each sequence is analysed independently</li>"
            "<li>Use <b>Export CSV</b> to open the composition table in Excel or R</li>"
            "</ul>"
        )
        from PyQt6.QtCore import Qt as QtCore
        from PyQt6.QtWidgets import (
            QDialog,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Help - Amino Acid Composition"))
        dlg.resize(600, 480)
        dlg.setMinimumSize(400, 300)
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(QtCore.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.AlignmentFlag.AlignTop | QtCore.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll.setWidget(label)
        layout.addWidget(scroll)
        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        layout.addWidget(ok)
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
        try:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                # Long format, one row per amino acid — same 4 columns as the table.
                writer.writerow(["Sequence_ID", "AA", "Count", "Percent"])
                for rec in self.current_results:
                    for aa in AMINO_ACIDS:
                        writer.writerow([
                            rec["header"],
                            aa,
                            rec["counts"][aa],
                            f"{rec['percents'][aa]:.2f}",
                        ])
            self._last_export_dir = os.path.dirname(file_path)
            self.open_folder_btn.setEnabled(True)
            self.status_label.setText(f"Exported: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
