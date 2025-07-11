from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QPlainTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from modules.fasta_processor import FASTAProcessor
import os

class ExtractByIDWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, input_path, id_list, output_path):
        super().__init__()
        self.input_path = input_path
        self.id_list = id_list
        self.output_path = output_path
    def run(self):
        try:
            processor = FASTAProcessor()
            if not processor.read_file(self.input_path):
                self.error.emit("无法读取FASTA文件")
                return
            id_set = set(i.strip() for i in self.id_list if i.strip())
            matched = []
            for record in processor.records:
                simple_id = record.header.split()[0]
                if simple_id in id_set:
                    matched.append(record)
            if not matched:
                self.error.emit("未找到任何匹配的ID")
                return
            if not processor.save_file(self.output_path, matched):
                self.error.emit("保存文件失败")
                return
            self.finished.emit(f"提取完成，找到{len(matched)}条序列，结果已保存到: {self.output_path}")
        except Exception as e:
            self.error.emit(str(e))

class ExtractByIDTab(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.worker = None
    def _init_ui(self):
        layout = QVBoxLayout()
        # 输入区
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入FASTA文件:"))
        self.input_edit = QLineEdit()
        input_layout.addWidget(self.input_edit)
        self.input_btn = QPushButton("浏览...")
        self.input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_btn)
        layout.addLayout(input_layout)
        # ID列表输入区
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("要提取的序列ID列表:"))
        self.id_edit = QPlainTextEdit()
        self.id_edit.setPlaceholderText("每行一个ID")
        id_layout.addWidget(self.id_edit)
        layout.addLayout(id_layout)
        # 输出区
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出提取的序列:"))
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        self.output_btn = QPushButton("另存为...")
        self.output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)
        # 执行区
        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始提取")
        self.run_btn.clicked.connect(self.run_extract)
        run_layout.addWidget(self.run_btn)
        self.progress = QLabel()
        run_layout.addWidget(self.progress)
        layout.addLayout(run_layout)
        # 日志区
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.setLayout(layout)
    def browse_input(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择FASTA文件", "", "FASTA files (*.fasta *.fa *.fas);;All files (*)")
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_extracted.fasta"))
    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存提取FASTA", "", "FASTA files (*.fasta *.fa *.fas);;All files (*)")
        if file_path:
            self.output_edit.setText(file_path)
    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        id_text = self.id_edit.toPlainText()
        id_list = id_text.splitlines()
        if not input_path or not os.path.isfile(input_path):
            self.log.append("[错误] 输入文件无效")
            return
        if not output_path:
            self.log.append("[错误] 输出文件路径无效")
            return
        if not id_list:
            self.log.append("[错误] ID列表不能为空")
            return
        self.run_btn.setEnabled(False)
        self.progress.setText("处理中...")
        self.worker = ExtractByIDWorker(input_path, id_list, output_path)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    def on_finished(self, msg):
        self.progress.setText("完成")
        self.log.append(msg)
        self.run_btn.setEnabled(True)
    def on_error(self, err):
        self.progress.setText("错误")
        self.log.append(f"[错误] {err}")
        self.run_btn.setEnabled(True) 