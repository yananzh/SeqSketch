from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QComboBox, QPlainTextEdit)
from PyQt6.QtCore import Qt
from utils.common_components import BaseWorker, BaseTabWidget
from urllib.error import URLError
import os


class DownloadFromNCBIWorker(BaseWorker):
    """从NCBI下载序列的工作线程"""
    
    def __init__(self, db, acc_list, output_path, email):
        super().__init__()
        self.db = db
        self.acc_list = acc_list
        self.output_path = output_path
        self.email = email
    
    def run(self):
        try:
            self.emit_progress("正在验证输入...")
            if not self.acc_list:
                self.emit_error("检索号列表为空")
                return
            
            if not self.email:
                self.emit_error("请提供邮箱地址（NCBI要求）")
                return
            
            self.emit_progress("正在连接NCBI...")
            try:
                from Bio import Entrez
            except ImportError:
                self.emit_error("需要安装Biopython库来下载NCBI数据")
                return
            
            Entrez.email = self.email
            ids = ','.join(self.acc_list)
            
            self.emit_progress(f"正在下载{len(self.acc_list)}个序列...")
            try:
                with Entrez.efetch(db=self.db, id=ids, rettype='fasta', retmode='text') as handle:
                    fasta_data = handle.read()
            except URLError as e:
                self.emit_error(f"网络连接错误: {e}")
                return
            except Exception as e:
                self.emit_error(f"NCBI下载错误: {e}")
                return
            
            if not fasta_data.strip() or 'Error' in fasta_data or 'not found' in fasta_data:
                self.emit_error("NCBI返回错误或未找到序列，请检查数据库类型和检索号是否正确")
                return
            
            self.emit_progress("正在保存文件...")
            try:
                # 确保输出目录存在
                os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write(fasta_data)
            except Exception as e:
                self.emit_error(f"文件保存失败: {e}")
                return
            
            seq_count = fasta_data.count('>')
            self.emit_finished(f"下载完成，共{seq_count}条序列，已保存到: {self.output_path}")
        except Exception as e:
            self.emit_error(f"下载过程中发生错误: {e}")


class DownloadFromNCBITab(BaseTabWidget):
    """从NCBI下载序列功能Tab"""
    
    def __init__(self):
        super().__init__("从NCBI下载序列", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 数据库选择
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("数据库:"))
        self.db_combo = QComboBox()
        self.db_combo.addItems([
            "nucleotide", "protein", "pubmed", "pmc", 
            "books", "clinvar", "gds", "geoprofiles"
        ])
        self.db_combo.setCurrentText("nucleotide")
        db_layout.addWidget(self.db_combo)
        db_layout.addStretch()
        
        # 邮箱输入
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("邮箱地址:"))
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("NCBI要求提供邮箱地址")
        email_layout.addWidget(self.email_edit)
        
        # 检索号输入
        acc_layout = QVBoxLayout()
        acc_layout.addWidget(QLabel("检索号列表（每行一个）:"))
        self.acc_edit = QPlainTextEdit()
        self.acc_edit.setPlaceholderText("输入检索号，每行一个\n例如:\nNM_001101.5\nNP_001092.1\nAF123456")
        self.acc_edit.setMaximumHeight(120)
        acc_layout.addWidget(self.acc_edit)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出文件:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("选择位置")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始下载")
        self.clear_btn = QPushButton("清空")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        # 添加到内容区域
        self.add_content_layout(db_layout)
        self.add_content_layout(email_layout)
        self.add_content_layout(acc_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_download)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存下载的序列", "", "FASTA文件 (*.fasta *.fa *.fas);;所有文件 (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.email_edit.clear()
        self.acc_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        self.db_combo.setCurrentText("nucleotide")
        self.show_status("已清空")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.db_combo.setEnabled(not running)
        self.email_edit.setEnabled(not running)
        self.acc_edit.setEnabled(not running)
    
    def run_download(self):
        db = self.db_combo.currentText()
        email = self.email_edit.text().strip()
        acc_text = self.acc_edit.toPlainText().strip()
        output_path = self.output_edit.text().strip()
        
        # 验证输入
        if not email:
            self.log_message("请输入邮箱地址（NCBI要求）", "ERROR")
            return
        
        if not acc_text:
            self.log_message("请输入检索号", "ERROR")
            return
        
        from utils.common_components import validate_output_path
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        # 处理检索号列表
        acc_list = [line.strip() for line in acc_text.split('\n') if line.strip()]
        if not acc_list:
            self.log_message("检索号列表为空", "ERROR")
            return
        
        # 启动工作线程
        worker = DownloadFromNCBIWorker(db, acc_list, output_path, email)
        self.start_worker(worker)
    
    def show_help(self):
        """显示帮助信息"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>NCBI序列下载工具</h3>
<p><b>功能说明：</b></p>
<p>根据检索号（Accession Number）从NCBI数据库批量下载序列数据。</p>

<p><b>使用方法：</b></p>
<ol>
<li>选择目标数据库（nucleotide或protein）</li>
<li>输入有效的邮箱地址（NCBI访问要求）</li>
<li>输入检索号列表（每行一个）</li>
<li>指定下载文件的保存位置</li>
<li>点击"开始下载"按钮</li>
</ol>

<p><b>支持的数据库：</b></p>
<ul>
<li><b>nucleotide：</b>核酸序列数据库（DNA/RNA）</li>
<li><b>protein：</b>蛋白质序列数据库</li>
</ul>

<p><b>检索号格式示例：</b></p>
<pre>
NM_001101.5
XM_123456.1
AF123456
U12345
AAA12345
</pre>

<p><b>邮箱要求：</b></p>
<p>NCBI要求在API访问时提供有效邮箱地址，用于：</p>
<ul>
<li>追踪API使用情况</li>
<li>在过度使用时发送通知</li>
<li>技术问题联系</li>
</ul>

<p><b>应用场景：</b></p>
<ul>
<li>批量下载已知检索号的序列</li>
<li>获取最新版本的参考序列</li>
<li>构建本地序列数据集</li>
</ul>

<p><b>注意事项：</b></p>
<ul>
<li>请遵守NCBI的使用政策，避免过频请求</li>
<li>网络连接质量会影响下载速度</li>
<li>无效的检索号会被跳过并记录</li>
</ul>

<p><b>输出格式：</b></p>
<p>下载的序列以标准FASTA格式保存，包含完整的序列信息和描述。</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("帮助 - NCBI序列下载")
        dialog.setFixedSize(800, 530)
        
        layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建文本标签
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(False)  # 禁用自动换行
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        
        # 添加确定按钮
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec()
