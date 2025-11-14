from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import csv
import re

AMINO_ACIDS = [
    'A', 'R', 'N', 'D', 'C', 'Q', 'E', 'G', 'H', 'I',
    'L', 'K', 'M', 'F', 'P', 'S', 'T', 'W', 'Y', 'V'
]

class AminoAcidCompositionTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Amino Acid Composition", "sequence")
        self.table = QTableWidget()
        self.add_content_widget(self.table)
        self.table.setVisible(False)
        self.export_btn.setText("Export CSV")
        self.export_btn.clicked.disconnect()
        self.export_btn.clicked.connect(self.export_csv)
        self.run_btn.setText("Analyze")
        self.help_btn.setText("Help")

    def run(self):
        self.status_label.setText("")
        self.table.setVisible(False)
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please input or load FASTA protein sequences.")
            return
        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "Format Error", str(e))
            return
        if not records:
            QMessageBox.warning(self, "Input Error", "No valid FASTA sequences detected.")
            return
        results = []
        for header, seq in records:
            seq = seq.upper()
            if not all(c in AMINO_ACIDS for c in seq):
                QMessageBox.warning(self, "Sequence Error", f"Sequence {header} contains non-standard amino acids.")
                return
            analysis = ProteinAnalysis(seq)
            freq = analysis.get_amino_acids_percent()
            row = [header] + [round(freq.get(aa, 0)*100, 2) for aa in AMINO_ACIDS]
            results.append(row)
        self.show_table(results)
        self.status_label.setText(f"Analyzed {len(results)} sequences.")

    def show_table(self, results):
        self.table.clear()
        self.table.setVisible(True)
        self.table.setColumnCount(1 + len(AMINO_ACIDS))
        self.table.setHorizontalHeaderLabels(["FASTA Title"] + AMINO_ACIDS)
        self.table.setRowCount(len(results))
        for i, row in enumerate(results):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if j > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()

    def export_csv(self):
        if not self.table.isVisible() or self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Please run analysis first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "amino_acid_composition.csv", "CSV Files (*.csv)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())])
                for row in range(self.table.rowCount()):
                    writer.writerow([self.table.item(row, col).text() for col in range(self.table.columnCount())])
            self.status_label.setText(f"Exported: {file_path}")

    def parse_fasta(self, text):
        records = []
        header = None
        seq_lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('>'):
                if header and seq_lines:
                    records.append((header, ''.join(seq_lines)))
                header = line[1:].strip()
                seq_lines = []
            else:
                if not re.match(r'^[A-Za-z*.-]+$', line):
                    raise ValueError(f"Sequence line contains invalid characters: {line}")
                seq_lines.append(line)
        if header and seq_lines:
            records.append((header, ''.join(seq_lines)))
        return records

    def show_help(self):
        QMessageBox.information(self, "Help - Amino Acid Composition", """
1. Paste or upload protein sequences in FASTA format.
2. Only 20 standard amino acids are supported (A, R, N, D, C, Q, E, G, H, I, L, K, M, F, P, S, T, W, Y, V).
3. The result is the percentage of each amino acid per sequence (two decimals), exportable to CSV.
4. Invalid input or non-standard characters will be prompted.
""") 
