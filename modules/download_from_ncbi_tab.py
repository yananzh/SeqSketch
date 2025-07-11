from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QComboBox, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os

class DownloadFromNCBIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    def __init__(self, db, acc_list, output_path, email):
        super().__init__()
        self.db = db
        self.acc_list = acc_list
        self.output_path = output_path
        self.email = email
    def run(self):
        try:
            self.progress.emit("正在连接NCBI...")
            from Bio import Entrez
            Entrez.email = self.email
            ids = ','.join(self.acc_list)
            from urllib.error import URLError
            try:
                with Entrez.efetch(db=self.db, id=ids, rettype='fasta', retmode='text') as handle:
                    fasta_data = handle.read()
            except URLError as e:
                self.error.emit(f"网络连接错误: {e}")
                return
            if not fasta_data.strip() or 'Error' in fasta_data or 'not found' in fasta_data:
                self.error.emit("NCBI返回错误或未找到序列，请检查检索号是否正确。")
                return
            try:
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write(fasta_data)
            except Exception as e:
                self.error.emit(f"文件保存失败: {e}")
                return
            self.finished.emit(f"下载完成，共{fasta_data.count('>')}条序列，已保存到: {self.output_path}")
        except Exception as e:
            self.error.emit(str(e))

class DownloadFromNCBITab(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.worker = None
    def _init_ui(self):
        layout = QVBoxLayout()
        # 数据库选择区
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("选择NCBI数据库:"))
        self.db_combo = QComboBox()
        self.db_combo.addItem("Nucleotide (nuccore)", 'nuccore')
        self.db_combo.addItem("Protein (protein)", 'protein')
        self.db_combo.setCurrentIndex(0)
        db_layout.addWidget(self.db_combo)
        layout.addLayout(db_layout)
        # 检索号输入区
        acc_layout = QVBoxLayout()
        acc_layout.addWidget(QLabel("输入检索号 (可用逗号、空格或换行分隔):"))
        self.acc_edit = QPlainTextEdit()
        self.acc_edit.setPlaceholderText("如: NM_001200, XP_005248, ...")
        acc_layout.addWidget(self.acc_edit)
        layout.addLayout(acc_layout)
        # 输出区
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("保存为FASTA文件:"))
        self.output_edit = QLineEdit()
        self.output_edit.setText(os.path.join(os.getcwd(), "ncbi_download.fasta"))
        output_layout.addWidget(self.output_edit)
        self.output_btn = QPushButton("另存为...")
        self.output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)
        # 邮箱区
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("NCBI邮箱(必填):"))
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("your.email@example.com")
        email_layout.addWidget(self.email_edit)
        layout.addLayout(email_layout)
        # 执行与状态区
        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始下载")
        self.run_btn.clicked.connect(self.run_download)
        run_layout.addWidget(self.run_btn)
        self.progress = QLabel()
        run_layout.addWidget(self.progress)
        layout.addLayout(run_layout)
        # 日志区
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.setLayout(layout)
    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存FASTA文件", "ncbi_download.fasta", "FASTA files (*.fasta *.fa *.fas);;All files (*)")
        if file_path:
            self.output_edit.setText(file_path)
    def run_download(self):
        db = self.db_combo.currentData()
        acc_text = self.acc_edit.toPlainText()
        email = self.email_edit.text().strip()
        output_path = self.output_edit.text().strip()
        # 解析检索号
        accs = [a.strip() for a in acc_text.replace(',', ' ').replace('\n', ' ').split() if a.strip()]
        accs = list(dict.fromkeys(accs))  # 去重
        if not accs:
            self.log.append("[错误] 检索号不能为空")
            return
        if not output_path:
            self.log.append("[错误] 输出文件路径无效")
            return
        if not email or '@' not in email:
            self.log.append("[错误] 请输入有效的NCBI邮箱")
            return
        self.run_btn.setEnabled(False)
        self.progress.setText("处理中...")
        self.worker = DownloadFromNCBIWorker(db, accs, output_path, email)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(self.on_progress)
        self.worker.start()
    def on_finished(self, msg):
        self.progress.setText("完成")
        self.log.append(msg)
        self.run_btn.setEnabled(True)
    def on_error(self, err):
        self.progress.setText("错误")
        self.log.append(f"[错误] {err}")
        self.run_btn.setEnabled(True)
    def on_progress(self, msg):
        self.progress.setText(msg) 