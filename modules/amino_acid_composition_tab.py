from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from .base_tab import BaseTabWidget
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import csv
import re

AMINO_ACIDS = [
    'A', 'R', 'N', 'D', 'C', 'Q', 'E', 'G', 'H', 'I',
    'L', 'K', 'M', 'F', 'P', 'S', 'T', 'W', 'Y', 'V'
]

class AminoAcidCompositionTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("氨基酸组成分析", parent)
        self.table = QTableWidget()
        self.layout().addWidget(self.table)
        self.table.setVisible(False)
        self.export_btn.setText("导出为CSV")
        self.export_btn.clicked.disconnect()
        self.export_btn.clicked.connect(self.export_csv)
        self.run_btn.setText("分析")
        self.help_btn.setText("帮助")

    def run(self):
        self.status_label.setText("")
        self.table.setVisible(False)
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "输入错误", "请输入或加载FASTA格式的蛋白质序列！")
            return
        try:
            records = self.parse_fasta(text)
        except Exception as e:
            QMessageBox.warning(self, "格式错误", str(e))
            return
        if not records:
            QMessageBox.warning(self, "输入错误", "未检测到有效的FASTA序列！")
            return
        results = []
        for header, seq in records:
            seq = seq.upper()
            if not all(c in AMINO_ACIDS for c in seq):
                QMessageBox.warning(self, "序列错误", f"序列 {header} 含有非标准氨基酸字符！")
                return
            analysis = ProteinAnalysis(seq)
            freq = analysis.get_amino_acids_percent()
            row = [header] + [round(freq.get(aa, 0)*100, 2) for aa in AMINO_ACIDS]
            results.append(row)
        self.show_table(results)
        self.status_label.setText(f"共分析 {len(results)} 条序列。")

    def show_table(self, results):
        self.table.clear()
        self.table.setVisible(True)
        self.table.setColumnCount(1 + len(AMINO_ACIDS))
        self.table.setHorizontalHeaderLabels(["FASTA标题"] + AMINO_ACIDS)
        self.table.setRowCount(len(results))
        for i, row in enumerate(results):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if j > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()

    def export_csv(self):
        if not self.table.isVisible() or self.table.rowCount() == 0:
            QMessageBox.warning(self, "无数据", "请先进行分析！")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为CSV", "amino_acid_composition.csv", "CSV文件 (*.csv)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())])
                for row in range(self.table.rowCount()):
                    writer.writerow([self.table.item(row, col).text() for col in range(self.table.columnCount())])
            self.status_label.setText(f"结果已导出: {file_path}")

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
                if not re.match(r'^[A-Za-z*.-]+$', line):
                    raise ValueError(f"序列行包含非法字符: {line}")
                seq_lines.append(line)
        if header and seq_lines:
            records.append((header, ''.join(seq_lines)))
        return records

    def show_help(self):
        QMessageBox.information(self, "氨基酸组成分析帮助", """
1. 支持粘贴或上传FASTA格式的蛋白质序列。
2. 仅支持20种标准氨基酸（A, R, N, D, C, Q, E, G, H, I, L, K, M, F, P, S, T, W, Y, V）。
3. 结果为每条序列20种氨基酸的百分比（保留两位小数），可导出为CSV。
4. 输入无效或含有非标准字符时会有提示。
""") 