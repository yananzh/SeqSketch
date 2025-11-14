from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox

class ComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("Complement", "sequence")

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA sequence.")
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText("Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc.")
            return
        comp = seq.translate(self.complement_map)
        self.output_text.setPlainText(comp)
        self.status_label.setText("Complement generated")

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, "Help - Complement", "Generate DNA complement: A↔T, G↔C. Supports IUPAC codes and mixed case input; N is unchanged.") 
