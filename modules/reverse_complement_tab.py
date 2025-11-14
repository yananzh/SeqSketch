from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox

class ReverseComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("Reverse Complement", "sequence")

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA sequence.")
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText("Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc.")
            return
        revcomp = seq.translate(self.complement_map)[::-1]
        self.output_text.setPlainText(revcomp)
        self.status_label.setText("Reverse complement generated")

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, "Help - Reverse Complement", "Generate complement then reverse it. Useful for molecular biology operations and primer design. Supports IUPAC codes and mixed case input.") 
