from PyQt6.QtWidgets import QMessageBox, QFileDialog
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import csv
import re

PROPERTIES = [
    ("Length (aa)", "length"),
    ("Molecular Weight (Da)", "molecular_weight"),
    ("Theoretical pI", "pi"),
    ("Aromaticity", "aromaticity"),
    ("Instability Index", "instability_index"),
    ("GRAVY", "gravy")
]

AMINO_ACIDS = [
    'A', 'R', 'N', 'D', 'C', 'Q', 'E', 'G', 'H', 'I',
    'L', 'K', 'M', 'F', 'P', 'S', 'T', 'W', 'Y', 'V'
]

class PhysicochemicalPropertiesTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Physicochemical Properties", "sequence")
        # Hide copy button per requirement
        if hasattr(self, 'copy_btn'):
            self.copy_btn.hide()
        # Wire export button to CSV export
        if hasattr(self, 'export_btn'):
            try:
                self.export_btn.clicked.disconnect()
            except Exception:
                pass
            self.export_btn.setText("Export CSV")
            self.export_btn.clicked.connect(self.export_csv)
        # Rename run/help buttons
        self.run_btn.setText("Analyze")
        self.help_btn.setText("Help")
        # Placeholder updates
        self.input_text.setPlaceholderText(
            "Paste protein sequence(s) in FASTA format or drag-and-drop a file...\n"
            ">seq1\nMKTFFVAGLMAGIS...\n>seq2\nMVLSEGEWQLVLHVWAKVEADVAGHGQDIL..." )
        self.output_text.setPlaceholderText("Computed physicochemical properties will appear here...")
        # Enable drag & drop
        self._setup_drag_drop()
        # Storage for results
        self.current_results = []

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
        self.current_results = []
        out_lines = []
        for header, seq in records:
            seq = seq.upper()
            if not all(c in AMINO_ACIDS for c in seq):
                QMessageBox.warning(self, "Sequence Error", f"Sequence {header} contains non-standard amino acid characters.")
                return
            analysis = ProteinAnalysis(seq)
            length = len(seq)
            mw = round(analysis.molecular_weight(), 2)
            pi = round(analysis.isoelectric_point(), 2)
            instab = round(analysis.instability_index(), 2)
            gravy = round(analysis.gravy(), 3)
            instab_str = f"{instab} (unstable)" if instab > 40 else f"{instab}"
            # Extinction coefficient (reduced / oxidized) at 280 nm (M^-1 cm^-1)
            ec_reduced, ec_oxidized = self.extinction_coefficient(seq)
            # Aliphatic index
            aliphatic_idx = round(self.aliphatic_index(seq), 2)
            # Estimated half-life (mammalian reticulocytes, in vitro)
            half_life = self.estimated_half_life_mammalian(seq)
            out_lines.append(f">{header} | Length: {length} aa")
            out_lines.append("Property                Value")
            out_lines.append(f"Molecular Weight (Da):  {mw}")
            out_lines.append(f"Theoretical pI:         {pi}")
            out_lines.append(f"Extinction Coeff. (280nm): reduced={ec_reduced} | oxidized={ec_oxidized}")
            out_lines.append(f"Estimated Half-life (mammalian): {half_life}")
            out_lines.append(f"Instability Index:      {instab_str}")
            out_lines.append(f"Aliphatic Index:        {aliphatic_idx}")
            out_lines.append(f"GRAVY:                  {gravy}")
            out_lines.append("")
            self.current_results.append({
                'header': header,
                'length': length,
                'molecular_weight': mw,
                'pi': pi,
                'ext_coeff_reduced': ec_reduced,
                'ext_coeff_oxidized': ec_oxidized,
                'half_life_mammalian': half_life,
                'instability_index': instab,
                'instability_unstable': instab > 40,
                'aliphatic_index': aliphatic_idx,
                'gravy': gravy
            })
        self.output_text.setPlainText('\n'.join(out_lines))
        self.status_label.setText(f"Analyzed {len(records)} sequences.")

    # Table-based display removed (output now in text box)

    def export_csv(self):
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please run analysis first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Physicochemical Properties CSV", "physicochemical_properties.csv", "CSV Files (*.csv)")
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Sequence_ID","Length","Molecular_Weight_Da","Theoretical_pI","ExtCoeff_Reduced","ExtCoeff_Oxidized","Estimated_Half_Life_Mammalian","Instability_Index","Unstable","Aliphatic_Index","GRAVY"])
                for rec in self.current_results:
                    writer.writerow([
                        rec['header'], rec['length'], rec['molecular_weight'], rec['pi'], rec['ext_coeff_reduced'], rec['ext_coeff_oxidized'],
                        rec['half_life_mammalian'], rec['instability_index'], 'Yes' if rec['instability_unstable'] else 'No', rec['aliphatic_index'], rec['gravy']
                    ])
            self.status_label.setText(f"Exported CSV: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

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
        QMessageBox.information(self, "Help - Physicochemical Properties", """
1. Paste or drag-and-drop protein sequences in FASTA format (multiple sequences supported).
2. Only 20 standard amino acids are allowed: A R N D C Q E G H I L K M F P S T W Y V.
3. Click Analyze to compute per sequence: Molecular Weight, Theoretical pI, Extinction Coefficient (reduced/oxidized), Estimated Half-life (mammalian, N-end rule), Instability Index (>40 unstable), Aliphatic Index, and GRAVY.
4. Results are shown in the output text area and can be exported to CSV.
5. Invalid input or non-standard characters will trigger a warning.
""") 

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

    def extinction_coefficient(self, seq: str) -> tuple[int, int]:
        """Return (reduced, oxidized) extinction coefficients at 280 nm (M^-1 cm^-1).
        Based on counts of Trp (W), Tyr (Y), and Cystine (Cys-Cys) pairs.
        reduced: 5500*#W + 1490*#Y
        oxidized: reduced + 125*(#Cys pairs)
        """
        w = seq.count('W')
        y = seq.count('Y')
        c = seq.count('C')
        reduced = 5500*w + 1490*y
        cystine_pairs = c // 2
        oxidized = reduced + 125 * cystine_pairs
        return reduced, oxidized

    def aliphatic_index(self, seq: str) -> float:
        """Calculate aliphatic index (Ikai) using mole fractions.
        AI = 100 * (X(Ala) + 2.9*X(Val) + 3.9*(X(Ile)+X(Leu)))
        """
        length = len(seq)
        if length == 0:
            return 0.0
        xa = seq.count('A') / length
        xv = seq.count('V') / length
        xile = (seq.count('I') + seq.count('L')) / length
        return 100.0 * (xa + 2.9 * xv + 3.9 * xile)

    def estimated_half_life_mammalian(self, seq: str) -> str:
        """Rough N-end rule-based estimate for mammalian reticulocytes (in vitro).
        Categories adapted from common N-end rule approximations.
        """
        if not seq:
            return "N/A"
        n = seq[0]
        stable_30h = set(list("ACGMPSTV"))
        mid_20h = set(list("ILFWY"))
        very_short_2m = set(list("KR"))
        short_3m = set(list("DEHQ"))
        if n in stable_30h:
            return "~30 hours"
        if n in mid_20h:
            return "~20 hours"
        if n in very_short_2m:
            return "~2 minutes"
        if n in short_3m:
            return "~3 minutes"
        # Default conservative fallback
        return ">= 20 hours"