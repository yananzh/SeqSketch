from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os

class BatchRenameIDsWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, fasta_path, mapping_path, has_header, output_path):
        super().__init__()
        self.fasta_path = fasta_path
        self.mapping_path = mapping_path
        self.has_header = has_header
        self.output_path = output_path
    def run(self):
        try:
            import pandas as pd
            # 读取映射文件
            ext = os.path.splitext(self.mapping_path)[1].lower()
            if ext in ['.xls', '.xlsx']:
                df = pd.read_excel(self.mapping_path, header=0 if self.has_header else None)
            elif ext in ['.csv']:
                df = pd.read_csv(self.mapping_path, header=0 if self.has_header else None)
            elif ext in ['.tsv', '.txt']:
                df = pd.read_csv(self.mapping_path, sep='\t', header=0 if self.has_header else None)
            else:
                self.error.emit("不支持的映射文件格式")
                return
            if df.shape[1] < 2:
                self.error.emit("映射文件至少应有两列（旧ID，新ID）")
                return
            mapping = dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(str)))
            # 读取FASTA
            from modules.fasta_processor import FASTAProcessor
            processor = FASTAProcessor()
            if not processor.read_file(self.fasta_path):
                self.error.emit("无法读取FASTA文件")
                return
            total = len(processor.records)
            renamed = 0
            unmatched = []
            for record in processor.records:
                simple_id = record.header.split()[0]
                if simple_id in mapping:
                    record.header = mapping[simple_id]
                    record.description = ''
                    renamed += 1
                else:
                    unmatched.append(simple_id)
            # 保存
            if not processor.save_file(self.output_path):
                self.error.emit("保存输出文件失败")
                return
            msg = f"处理完成，共{total}条序列，成功重命名{renamed}条。"
            if unmatched:
                msg += f"\n未匹配到的ID（共{len(unmatched)}条）: " + ', '.join(unmatched)
            self.finished.emit(msg)
        except Exception as e:
            self.error.emit(str(e))

class BatchRenameIDsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.worker = None
    def _init_ui(self):
        layout = QVBoxLayout()
        # FASTA输入区
        fasta_layout = QHBoxLayout()
        fasta_layout.addWidget(QLabel("输入原始FASTA文件:"))
        self.fasta_edit = QLineEdit()
        fasta_layout.addWidget(self.fasta_edit)
        self.fasta_btn = QPushButton("浏览...")
        self.fasta_btn.clicked.connect(self.browse_fasta)
        fasta_layout.addWidget(self.fasta_btn)
        layout.addLayout(fasta_layout)
        # 映射文件输入区
        mapping_layout = QHBoxLayout()
        mapping_layout.addWidget(QLabel("输入ID映射文件:"))
        self.mapping_edit = QLineEdit()
        mapping_layout.addWidget(self.mapping_edit)
        self.mapping_btn = QPushButton("浏览...")
        self.mapping_btn.clicked.connect(self.browse_mapping)
        mapping_layout.addWidget(self.mapping_btn)
        # 文件类型提示
        mapping_layout.addWidget(QLabel("(支持: Excel, TSV, CSV)"))
        layout.addLayout(mapping_layout)
        # 映射文件选项
        self.header_checkbox = QCheckBox("映射文件包含表头")
        layout.addWidget(self.header_checkbox)
        # 输出区
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出重命名后的FASTA文件:"))
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        self.output_btn = QPushButton("另存为...")
        self.output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)
        # 执行与状态区
        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始重命名")
        self.run_btn.clicked.connect(self.run_rename)
        run_layout.addWidget(self.run_btn)
        layout.addLayout(run_layout)
        # 日志区
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.setLayout(layout)
    def browse_fasta(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择FASTA文件", "", "FASTA files (*.fasta *.fa *.fas);;All files (*)")
        if file_path:
            self.fasta_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_renamed.fasta"))
    def browse_mapping(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择ID映射文件", "", "Excel/TSV/CSV files (*.xls *.xlsx *.tsv *.txt *.csv);;All files (*)")
        if file_path:
            self.mapping_edit.setText(file_path)
    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存重命名FASTA", "", "FASTA files (*.fasta *.fa *.fas);;All files (*)")
        if file_path:
            self.output_edit.setText(file_path)
    def run_rename(self):
        fasta_path = self.fasta_edit.text().strip()
        mapping_path = self.mapping_edit.text().strip()
        output_path = self.output_edit.text().strip()
        has_header = self.header_checkbox.isChecked()
        if not fasta_path or not os.path.isfile(fasta_path):
            self.log.append("[错误] 输入FASTA文件无效")
            return
        if not mapping_path or not os.path.isfile(mapping_path):
            self.log.append("[错误] 映射文件无效")
            return
        if not output_path:
            self.log.append("[错误] 输出文件路径无效")
            return
        self.run_btn.setEnabled(False)
        self.log.append("[信息] 开始处理...")
        self.worker = BatchRenameIDsWorker(fasta_path, mapping_path, has_header, output_path)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    def on_finished(self, msg):
        self.log.append(msg)
        self.run_btn.setEnabled(True)
    def on_error(self, err):
        self.log.append(f"[错误] {err}")
        self.run_btn.setEnabled(True) 