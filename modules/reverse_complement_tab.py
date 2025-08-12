from utils.common_components import BaseTabWidget
import translations
import re
from PyQt6.QtWidgets import QMessageBox

class ReverseComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("反向互补序列", "sequence")

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText(translations.tr("请输入DNA序列！"))
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText(translations.tr("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！"))
            return
        revcomp = seq.translate(self.complement_map)[::-1]
        self.output_text.setPlainText(revcomp)
        self.status_label.setText(translations.tr("已生成反向互补序列"))

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, translations.tr("反向互补序列 帮助"), translations.tr("先生成互补序列，再反向排列。常用于分子生物学操作和引物设计。支持IUPAC代码和大小写输入。"))
    
    def update_language(self):
        """Update UI elements when language changes"""
        # Update status messages if currently displayed
        current_status = self.status_label.text()
        if "请输入DNA序列" in current_status or "Please enter DNA sequence" in current_status:
            self.status_label.setText(translations.tr("请输入DNA序列！"))
        elif "已生成反向互补序列" in current_status or "Generated reverse complement sequence" in current_status:
            self.status_label.setText(translations.tr("已生成反向互补序列"))
        elif "输入序列包含无效字符" in current_status or "Input sequence contains invalid characters" in current_status:
            self.status_label.setText(translations.tr("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！"))
        super().update_language() 