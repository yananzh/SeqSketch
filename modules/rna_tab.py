from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox

class RNATab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Convert to RNA", "sequence")

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("Please enter a DNA sequence.")
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText("Invalid characters. Allowed IUPAC codes: A/T/G/C/N, etc.")
            return
        rna = seq.upper().replace('T', 'U').replace('t', 'u')
        self.output_text.setPlainText(rna)
        self.status_label.setText("Converted to RNA")

    def is_valid_dna(self, seq):
        # 允许IUPAC核苷酸代码
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, "Help - Convert to RNA", "Replace T (Thymine) with U (Uracil) in DNA sequences. Supports IUPAC codes and mixed case input.") 
