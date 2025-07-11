from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt

class BaseTabWidget(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 输入区域
        self.input_label = QLabel("输入序列或上传文件：")
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("粘贴DNA/RNA序列，或点击下方按钮上传文件...")
        self.upload_btn = QPushButton("上传文件")
        self.upload_btn.clicked.connect(self.open_file)
        self.input_hint = QLabel("")
        self.input_hint.setStyleSheet("color: #888;")

        input_layout = QVBoxLayout()
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_text)
        input_layout.addWidget(self.upload_btn)
        input_layout.addWidget(self.input_hint)

        # 输出区域
        self.output_label = QLabel("输出结果：")
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.export_btn = QPushButton("导出结果")
        self.copy_btn = QPushButton("复制到剪贴板")
        self.export_btn.clicked.connect(self.export_result)
        self.copy_btn.clicked.connect(self.copy_result)

        output_btn_layout = QHBoxLayout()
        output_btn_layout.addWidget(self.export_btn)
        output_btn_layout.addWidget(self.copy_btn)

        output_layout = QVBoxLayout()
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_text)
        output_layout.addLayout(output_btn_layout)

        # 控制按钮
        self.run_btn = QPushButton("运行")
        self.clear_btn = QPushButton("清空")
        self.help_btn = QPushButton("帮助")
        self.run_btn.clicked.connect(self.run)
        self.clear_btn.clicked.connect(self.clear)
        self.help_btn.clicked.connect(self.show_help)

        ctrl_btn_layout = QHBoxLayout()
        ctrl_btn_layout.addWidget(self.run_btn)
        ctrl_btn_layout.addWidget(self.clear_btn)
        ctrl_btn_layout.addWidget(self.help_btn)
        ctrl_btn_layout.addStretch()

        # 状态栏
        self.status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)

        # 组装
        layout.addLayout(input_layout)
        layout.addLayout(output_layout)
        layout.addLayout(ctrl_btn_layout)
        layout.addLayout(status_layout)
        self.setLayout(layout)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择序列文件", "", "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;所有文件 (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"已加载文件: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "文件读取错误", str(e))

    def export_result(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出结果", "result.txt", "文本文件 (*.txt);;FASTA文件 (*.fasta);;CSV文件 (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                self.status_label.setText(f"结果已导出: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "导出错误", str(e))

    def copy_result(self):
        self.output_text.selectAll()
        self.output_text.copy()
        self.status_label.setText("结果已复制到剪贴板")

    def run(self):
        # 由子类实现
        pass

    def clear(self):
        self.input_text.clear()
        self.output_text.clear()
        self.status_label.clear()
        self.input_hint.clear()
        self.progress_bar.setVisible(False)

    def show_help(self):
        # 由子类实现
        pass 