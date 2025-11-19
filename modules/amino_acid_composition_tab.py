from PyQt6.QtWidgets import QMessageBox, QFileDialog
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import re
import csv

AMINO_ACIDS = [
    'A', 'R', 'N', 'D', 'C', 'Q', 'E', 'G', 'H', 'I',
    'L', 'K', 'M', 'F', 'P', 'S', 'T', 'W', 'Y', 'V'
]

class AminoAcidCompositionTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Amino Acid Composition", "sequence")
        # Customize buttons/text
        self.run_btn.setText("Analyze")
        # Hide copy button per requirement
        if hasattr(self, 'copy_btn'):
            self.copy_btn.hide()
        # Re-wire export to CSV
        if hasattr(self, 'export_btn'):
            try:
                self.export_btn.clicked.disconnect()
            except Exception:
                pass
            self.export_btn.setText("Export CSV")
            self.export_btn.clicked.connect(self.export_csv)
        # storage for current results
        self.current_results = []
        # Update placeholders for protein sequences
        self.input_text.setPlaceholderText(
            "Paste protein sequence(s) in FASTA format or drag-and-drop a file...\n"
            "Examples:\n>prot1\nMKTFFVAGLMAGIS\n>prot2\nMVLSEGEWQLVLHVWAKVEADVAGHGQDIL" )
        self.output_text.setPlaceholderText("Amino acid composition (counts and percentages) will appear here...")
        # Enable drag-and-drop
        self._setup_drag_drop()

    def run(self):
        self.status_label.setText("")
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
        output_lines = []
        self.current_results = []
        for header, seq in records:
            seq = seq.upper()
            if not all(c in AMINO_ACIDS for c in seq):
                QMessageBox.warning(self, "Sequence Error", f"Sequence {header} contains non-standard amino acids.")
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
                'header': header,
                'length': total_len,
                'counts': {aa: seq.count(aa) for aa in AMINO_ACIDS},
                'percents': {aa: freq.get(aa, 0) * 100 for aa in AMINO_ACIDS}
            })
            output_lines.append("")
        self.output_text.setPlainText('\n'.join(output_lines))
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
                with open(file_path, 'r', encoding='utf-8') as f:
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
            if line.startswith('>'):
                if header and seq_lines:
                    records.append((header, ''.join(seq_lines)))
                header = line[1:].strip()
                seq_lines = []
            else:
                if not re.match(r'^[A-Za-z]+$', line):
                    raise ValueError(f"Sequence line contains invalid characters: {line}")
                seq_lines.append(line)
        if header and seq_lines:
            records.append((header, ''.join(seq_lines)))
        return records

    def show_help(self):
        QMessageBox.information(self, "Help - Amino Acid Composition", """
1. Paste or drag-and-drop protein sequences in FASTA format (multiple sequences supported).
2. Only the 20 standard amino acids are allowed: A R N D C Q E G H I L K M F P S T W Y V.
3. Click Analyze to compute, for each sequence, the count and percentage of every amino acid.
4. Output format per sequence:
   >header | Length: N aa\nAA  Count  Percent\n...
5. Percentages are based on total sequence length (two decimals).
6. Use Export Result to save the composition text if needed.
""") 

    def export_csv(self):
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please run analysis first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Amino Acid Composition CSV", "amino_acid_composition.csv", "CSV Files (*.csv)")
        if not file_path:
            return
        # Prepare header: header,length, then per AA count and percent
        header_cols = ["Sequence_ID", "Length"]
        for aa in AMINO_ACIDS:
            header_cols.append(f"{aa}_count")
            header_cols.append(f"{aa}_percent")
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header_cols)
                for rec in self.current_results:
                    row = [rec['header'], rec['length']]
                    for aa in AMINO_ACIDS:
                        row.append(rec['counts'][aa])
                        row.append(f"{rec['percents'][aa]:.2f}")
                    writer.writerow(row)
            self.status_label.setText(f"Exported CSV: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
