from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QComboBox, QPlainTextEdit, QSizePolicy)
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from urllib.error import URLError
import os

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
        self.db_combo.setMinimumWidth(140)
        db_layout.addWidget(self.db_combo)
        db_layout.addStretch()
        
        # Email input
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("Email:"))
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("NCBI requires an email address")
        self.email_edit.setMinimumWidth(320)
        self.email_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        # Enlarge input area
        self.acc_edit.setMinimumHeight(200)
        self.acc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        acc_layout.addWidget(self.acc_edit)
        
        # Output file selection
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the downloaded FASTA...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # Control buttons
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Download")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        
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

        # 单线程执行下载
        self.set_running_state(True)
        try:
            self.show_status("Connecting to NCBI...")
            try:
                from Bio import Entrez
            except ImportError:
                self.log_message("Biopython (Bio.Entrez) is required to download NCBI data", "ERROR")
                return
            Entrez.email = email
            ids = ','.join(acc_list)
            self.show_status(f"Downloading {len(acc_list)} sequences...")
            try:
                with Entrez.efetch(db=db, id=ids, rettype='fasta', retmode='text') as handle:
                    fasta_data = handle.read()
            except URLError as e:
                self.log_message(f"Network error: {e}", "ERROR")
                return
            except Exception as e:
                self.log_message(f"NCBI download error: {e}", "ERROR")
                return
            if not fasta_data.strip() or 'Error' in fasta_data or 'not found' in fasta_data:
                self.log_message("NCBI returned error or no sequences found. Check DB type and accessions.", "ERROR")
                return
            self.show_status("Saving file...")
            try:
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(fasta_data)
            except Exception as e:
                self.log_message(f"File save failed: {e}", "ERROR")
                return
            seq_count = fasta_data.count('>')
            self.log_message(f"Download complete. {seq_count} sequences saved to: {output_path}")
        except Exception as e:
            import traceback
            self.log_message(f"Error during download: {e}\n{traceback.format_exc()}", "ERROR")
        finally:
            self.set_running_state(False)
    
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
