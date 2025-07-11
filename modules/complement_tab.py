from .base_tab import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox

class ComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("互补序列", parent)

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("请输入DNA序列！")
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！")
            return
        comp = seq.translate(self.complement_map)
        self.output_text.setPlainText(comp)
        self.status_label.setText("已生成互补序列")

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, "互补序列 帮助", "生成DNA的互补序列：A↔T，G↔C，支持IUPAC代码和大小写输入，N保持不变。") 