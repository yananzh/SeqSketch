from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QFileDialog, QTextEdit, QMessageBox
from PyQt6.QtCore import Qt
from Bio.Blast import NCBIXML
import csv
import os

class BlastResultTab(QWidget):
    def __init__(self, xml_path, parent=None):
        super().__init__(parent)
        self.xml_path = xml_path
        self.setWindowTitle(f"BLAST结果: {os.path.basename(xml_path)}")
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Query ID", "Subject ID", "Identity %", "E-value", "Score", "Align Len", "Description"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self.show_detail)
        layout.addWidget(self.table)
        # 导出按钮
        btn_layout = QHBoxLayout()
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_table('csv'))
        self.export_tsv_btn = QPushButton("导出TSV")
        self.export_tsv_btn.clicked.connect(lambda: self.export_table('tsv'))
        self.export_html_btn = QPushButton("导出HTML")
        self.export_html_btn.clicked.connect(self.export_html)
        btn_layout.addWidget(self.export_csv_btn)
        btn_layout.addWidget(self.export_tsv_btn)
        btn_layout.addWidget(self.export_html_btn)
        layout.addLayout(btn_layout)
        # 详情区
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        layout.addWidget(self.detail_text)
        self.setLayout(layout)
        self.records = []
        self.load_xml()
    def load_xml(self):
        try:
            with open(self.xml_path, 'r', encoding='utf-8') as f:
                blast_records = list(NCBIXML.parse(f))
        except Exception as e:
            QMessageBox.critical(self, "解析错误", f"BLAST XML解析失败: {e}")
            return
        rows = []
        for record in blast_records:
            qid = record.query
            for alignment in record.alignments:
                sid = alignment.hit_id
                desc = alignment.hit_def
                for hsp in alignment.hsps:
                    identity = round(100 * hsp.identities / hsp.align_length, 2) if hsp.align_length else 0
                    rows.append([
                        qid, sid, identity, hsp.expect, hsp.score, hsp.align_length, desc
                    ])
                    self.records.append((qid, sid, identity, hsp.expect, hsp.score, hsp.align_length, desc, hsp))
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if j in [2,3,4,5]:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()
    def show_detail(self, row, col):
        if row < 0 or row >= len(self.records):
            self.detail_text.clear()
            return
        qid, sid, identity, expect, score, alen, desc, hsp = self.records[row]
        detail = f"Query: {qid}\nSubject: {sid}\nDescription: {desc}\nIdentity: {identity}%\nE-value: {expect}\nScore: {score}\nAlignment length: {alen}\n\nQuery seq:  {hsp.query}\n            {hsp.match}\nSbjct seq:  {hsp.sbjct}"
        self.detail_text.setPlainText(detail)
    def export_table(self, fmt):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "无数据", "没有可导出的结果！")
            return
        ext = fmt
        sep = ',' if fmt == 'csv' else '\t'
        file_path, _ = QFileDialog.getSaveFileName(self, f"导出为{fmt.upper()}", f"blast_result.{ext}", f"{fmt.upper()}文件 (*.{ext})")
        if file_path:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=sep)
                writer.writerow([self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())])
                for row in range(self.table.rowCount()):
                    writer.writerow([self.table.item(row, col).text() for col in range(self.table.columnCount())])
            QMessageBox.information(self, "导出成功", f"结果已导出: {file_path}")
    def export_html(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "无数据", "没有可导出的结果！")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出为HTML", "blast_result.html", "HTML文件 (*.html)")
        if file_path:
            html = '<table border="1"><tr>' + ''.join(f'<th>{self.table.horizontalHeaderItem(i).text()}</th>' for i in range(self.table.columnCount())) + '</tr>'
            for row in range(self.table.rowCount()):
                html += '<tr>' + ''.join(f'<td>{self.table.item(row, col).text()}</td>' for col in range(self.table.columnCount())) + '</tr>'
            html += '</table>'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html)
            QMessageBox.information(self, "导出成功", f"结果已导出: {file_path}") 