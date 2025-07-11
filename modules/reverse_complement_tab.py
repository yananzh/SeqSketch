from .base_tab import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox

class ReverseComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("反向互补序列", parent)

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("请输入DNA序列！")
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！")
            return
        revcomp = seq.translate(self.complement_map)[::-1]
        self.output_text.setPlainText(revcomp)
        self.status_label.setText("已生成反向互补序列")

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, "反向互补序列 帮助", "先生成互补序列，再反向排列。常用于分子生物学操作和引物设计。支持IUPAC代码和大小写输入。") 