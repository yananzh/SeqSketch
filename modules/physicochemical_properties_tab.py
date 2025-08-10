from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import csv
import re

PROPERTIES = [
    ("序列长度", "length"),
    ("分子量(Da)", "molecular_weight"),
    ("理论等电点(pI)", "pi"),
    ("芳香性", "aromaticity"),
    ("不稳定指数", "instability_index"),
    ("GRAVY", "gravy")
]

AMINO_ACIDS = [
    'A', 'R', 'N', 'D', 'C', 'Q', 'E', 'G', 'H', 'I',
    'L', 'K', 'M', 'F', 'P', 'S', 'T', 'W', 'Y', 'V'
]

class PhysicochemicalPropertiesTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("物化性质计算", "sequence")
        self.table = QTableWidget()
        self.add_content_widget(self.table)
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
            row = [header]
            row.append(len(seq))
            row.append(round(analysis.molecular_weight(), 2))
            row.append(round(analysis.isoelectric_point(), 2))
            row.append(round(analysis.aromaticity(), 3))
            instab = round(analysis.instability_index(), 2)
            row.append(f"{instab} (不稳定)" if instab > 40 else f"{instab}")
            row.append(round(analysis.gravy(), 3))
            results.append(row)
        self.show_table(results)
        self.status_label.setText(f"共分析 {len(results)} 条序列。")

    def show_table(self, results):
        self.table.clear()
        self.table.setVisible(True)
        self.table.setColumnCount(1 + len(PROPERTIES))
        self.table.setHorizontalHeaderLabels(["FASTA标题"] + [p[0] for p in PROPERTIES])
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
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为CSV", "physicochemical_properties.csv", "CSV文件 (*.csv)")
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
        QMessageBox.information(self, "物化性质计算帮助", """
1. 支持粘贴或上传FASTA格式的蛋白质序列。
2. 仅支持20种标准氨基酸（A, R, N, D, C, Q, E, G, H, I, L, K, M, F, P, S, T, W, Y, V）。
3. 计算内容：序列长度、分子量、理论等电点、芳香性、不稳定指数（>40为不稳定）、GRAVY。
4. 结果可导出为CSV。
5. 输入无效或含有非标准字符时会有提示。
""") 