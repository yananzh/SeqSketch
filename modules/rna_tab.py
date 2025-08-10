from utils.common_components import BaseTabWidget
import re
from PyQt6.QtWidgets import QMessageBox

class RNATab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("转成RNA", "sequence")

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText("请输入DNA序列！")
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！")
            return
        rna = seq.upper().replace('T', 'U').replace('t', 'u')
        self.output_text.setPlainText(rna)
        self.status_label.setText("已转换为RNA序列")

    def is_valid_dna(self, seq):
        # 允许IUPAC核苷酸代码
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, "转成RNA 帮助", "将DNA序列中的T（胸腺嘧啶）替换为U（尿嘧啶），支持IUPAC代码和大小写输入。") 