from utils.common_components import BaseTabWidget
import translations
import re
from PyQt6.QtWidgets import QMessageBox

class ComplementTab(BaseTabWidget):
    complement_map = str.maketrans(
        'ACGTacgtRYMKSWBDHVNrymkswbdhvn',
        'TGCAtgcaYRKMWSVHDBNyrkmwsvhdbn'
    )

    def __init__(self, parent=None):
        super().__init__("互补序列", "sequence")

    def run(self):
        seq = self.input_text.toPlainText().strip()
        if not seq:
            self.status_label.setText(translations.tr("请输入DNA序列！"))
            return
        if not self.is_valid_dna(seq):
            self.status_label.setText(translations.tr("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！"))
            return
        comp = seq.translate(self.complement_map)
        self.output_text.setPlainText(comp)
        self.status_label.setText(translations.tr("已生成互补序列"))

    def is_valid_dna(self, seq):
        return re.fullmatch(r'[ACGTNacgtnRYMKSWBDHVrykmswbdhv\s]+', seq) is not None

    def show_help(self):
        QMessageBox.information(self, translations.tr("互补序列 帮助"), translations.tr("生成DNA的互补序列：A↔T，G↔C，支持IUPAC代码和大小写输入，N保持不变。"))
    
    def update_language(self):
        """Update UI elements when language changes"""
        # Update status messages if currently displayed
        current_status = self.status_label.text()
        if "请输入DNA序列" in current_status or "Please enter DNA sequence" in current_status:
            self.status_label.setText(translations.tr("请输入DNA序列！"))
        elif "已生成互补序列" in current_status or "Generated complement sequence" in current_status:
            self.status_label.setText(translations.tr("已生成互补序列"))
        elif "输入序列包含无效字符" in current_status or "Input sequence contains invalid characters" in current_status:
            self.status_label.setText(translations.tr("输入序列包含无效字符，仅允许A/T/G/C/N等IUPAC代码！"))
        super().update_language() 