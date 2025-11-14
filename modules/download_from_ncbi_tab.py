from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QComboBox, QPlainTextEdit)
from PyQt6.QtCore import Qt
from utils.common_components import BaseWorker, BaseTabWidget
from urllib.error import URLError
import os


class DownloadFromNCBIWorker(BaseWorker):
    """Worker for downloading sequences from NCBI"""
    
    def __init__(self, db, acc_list, output_path, email):
        super().__init__()
        self.db = db
        self.acc_list = acc_list
        self.output_path = output_path
        self.email = email
    
    def run(self):
        try:
            self.emit_progress("Validating input...")
            if not self.acc_list:
                self.emit_error("Accession list is empty")
                return
            
            if not self.email:
                self.emit_error("Please provide an email (NCBI requirement)")
                return
            
            self.emit_progress("Connecting to NCBI...")
            try:
                from Bio import Entrez
            except ImportError:
                self.emit_error("Biopython is required to download NCBI data")
                return
            
            Entrez.email = self.email
            ids = ','.join(self.acc_list)
            
            self.emit_progress(f"Downloading {len(self.acc_list)} sequences...")
            try:
                with Entrez.efetch(db=self.db, id=ids, rettype='fasta', retmode='text') as handle:
                    fasta_data = handle.read()
            except URLError as e:
                self.emit_error(f"Network error: {e}")
                return
            except Exception as e:
                self.emit_error(f"NCBI download error: {e}")
                return
            
            if not fasta_data.strip() or 'Error' in fasta_data or 'not found' in fasta_data:
                self.emit_error("NCBI returned error or no sequences found. Check DB type and accessions.")
                return
            
            self.emit_progress("Saving file...")
            try:
                # Ensure output directory exists
                os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write(fasta_data)
            except Exception as e:
                self.emit_error(f"File save failed: {e}")
                return
            
            seq_count = fasta_data.count('>')
            self.emit_finished(f"Download complete. {seq_count} sequences saved to: {self.output_path}")
        except Exception as e:
            self.emit_error(f"Error during download: {e}")


class DownloadFromNCBITab(BaseTabWidget):
    """NCBI download Tab"""
    
    def __init__(self):
        super().__init__("Download from NCBI", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # Database selection
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database:"))
        self.db_combo = QComboBox()
        self.db_combo.addItems([
            "nucleotide", "protein"
        ])
        self.db_combo.setCurrentText("nucleotide")
        db_layout.addWidget(self.db_combo)
        db_layout.addStretch()
        
        # Email input
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("Email:"))
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("NCBI requires an email address")
        email_layout.addWidget(self.email_edit)
        
        # Accession input
        acc_layout = QVBoxLayout()
        acc_layout.setSpacing(1)
        acc_layout.setContentsMargins(0, 0, 0, 0)
        acc_label = QLabel("Accession list (one per line):")
        acc_label.setContentsMargins(0, 0, 0, 0)
        acc_layout.addWidget(acc_label)
        self.acc_edit = QPlainTextEdit()
        self.acc_edit.setPlaceholderText("Enter accession numbers, one per line\nExamples:\nNM_001101.5\nNP_001092.1\nAF123456")
        self.acc_edit.setMaximumHeight(120)
        acc_layout.addWidget(self.acc_edit)
        
        # Output file selection
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("Save As")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # Control buttons
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Download")
        self.clear_btn = QPushButton("Clear")
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
            self, "Save downloaded sequences", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.email_edit.clear()
        self.acc_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        self.db_combo.setCurrentText("nucleotide")
        self.show_status("Cleared")
    
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
        """Show help information"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>NCBI Sequence Downloader</h3>
<p><b>Description:</b></p>
<p>Batch download sequences from NCBI by accession numbers.</p>

<p><b>Usage:</b></p>
<ol>
<li>Select target database (nucleotide or protein)</li>
<li>Enter a valid email (required by NCBI)</li>
<li>Enter accession list (one per line)</li>
<li>Choose output file location</li>
<li>Click "Download"</li>
</ol>

<p><b>Databases:</b></p>
<ul>
<li><b>nucleotide:</b> DNA/RNA sequence database</li>
<li><b>protein:</b> Protein sequence database</li>
</ul>

<p><b>Accession examples:</b></p>
<pre>
NM_001101.5
XM_123456.1
AF123456
U12345
AAA12345
</pre>

<p><b>Email requirement:</b></p>
<p>NCBI requires a valid email for:</p>
<ul>
<li>Tracking API usage</li>
<li>Notification on excessive usage</li>
<li>Technical contact</li>
</ul>

<p><b>Use cases:</b></p>
<ul>
<li>Batch download sequences by known accessions</li>
<li>Get the latest reference sequences</li>
<li>Build local sequence datasets</li>
</ul>

<p><b>Notes:</b></p>
<ul>
<li>Follow NCBI usage policies and avoid excessive requests</li>
<li>Network quality affects speed</li>
<li>Invalid accessions will be skipped and logged</li>
</ul>

<p><b>Output:</b></p>
<p>Sequences are saved in standard FASTA format with full headers.</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - NCBI Downloader")
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
        
        # Add OK button
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec()
