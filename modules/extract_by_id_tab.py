from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QPlainTextEdit)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class ExtractByIDWorker(FASTAWorker):
    """Worker to extract sequences by ID"""
    
    def __init__(self, input_path, id_list, output_path):
        super().__init__(input_path, output_path)
        self.id_list = id_list
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("Loading FASTA file...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("Processing ID list...")
            id_set = set(i.strip() for i in self.id_list if i.strip())
            if not id_set:
                self.emit_error("ID list is empty")
                return
            
            self.emit_progress("Matching sequences...")
            matched = []
            for record in processor.records:
                simple_id = record.header.split()[0]
                if simple_id in id_set:
                    matched.append(record)
            
            if not matched:
                self.emit_error("No matching IDs found")
                return
            
            self.emit_progress("Saving results...")
            if not processor.save_file(self.output_path, matched):
                self.emit_error("Failed to save file")
                return
            
            self.emit_finished(f"Extraction complete. Found {len(matched)} sequences. Saved to: {self.output_path}")
        except Exception as e:
            self.emit_error(f"Error during extraction: {e}")


class ExtractByIDTab(BaseTabWidget):
    """Extract by ID Tab"""
    
    def __init__(self):
        super().__init__("Extract by ID", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 设置内容区域的间距和对齐
        self.content_area.setSpacing(8)  # 适中的组件间距
        
        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input FASTA file:"))
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton("Browse")
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        
        # ID列表输入区标签
        id_label = QLabel("Sequence IDs to extract (one per line):")
        
        # ID输入框
        self.id_edit = QPlainTextEdit()
        self.id_edit.setPlaceholderText("Enter sequence IDs, one per line\nExamples:\nseq1\nseq2\nseq3")
        self.id_edit.setFixedHeight(120)  # 增大高度以便输入更多ID
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("Save As")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_widget(id_label)
        self.add_content_widget(self.id_edit)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
        
        # 添加拉伸项，确保内容顶部对齐
        self.content_area.addStretch()
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_extract)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FASTA file", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_extracted.fasta"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save extracted sequences", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.id_edit.clear()
        self.log_area.clear()
        self.show_status("Cleared")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.id_edit.setEnabled(not running)
    
    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        id_text = self.id_edit.toPlainText().strip()
        
        # 验证输入
        from utils.common_components import validate_input_path, validate_output_path
        
        valid, error = validate_input_path(input_path, ['.fasta', '.fa', '.fas'])
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        if not id_text:
            self.log_message("Please enter sequence IDs to extract", "ERROR")
            return
        
        # 处理ID列表
        id_list = [line.strip() for line in id_text.split('\n') if line.strip()]
        if not id_list:
            self.log_message("ID list is empty", "ERROR")
            return
        
        # 启动工作线程
        worker = ExtractByIDWorker(input_path, id_list, output_path)
        self.start_worker(worker)
    
    def show_help(self):
        """Show help information"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>Extract Sequences by ID</h3>
<p><b>Description:</b></p>
<p>Extract sequences from a FASTA file using a provided list of IDs.</p>

<p><b>Usage:</b></p>
<ol>
<li>Select the source FASTA file</li>
<li>Choose where to save the results</li>
<li>Enter the sequence IDs (one per line)</li>
<li>Click "Start"</li>
</ol>

<p><b>ID input examples:</b></p>
<pre>
sequence_001
NM_001101.5
gi|123456|ref|XM_001234.1|
</pre>

<p><b>Matching rules:</b></p>
<ul>
<li>Exact match</li>
<li>Case-insensitive</li>
<li>Empty lines and whitespace ignored</li>
</ul>

<p><b>Use cases:</b></p>
<ul>
<li>Extract specific genes from large databases</li>
<li>Select target sequences based on analysis</li>
<li>Batch extraction of sequence subsets</li>
</ul>

<p><b>Output:</b></p>
<p>A new FASTA file containing all matched sequences, preserving original formatting.</p>
<p>Shows the number of sequences found and progress.</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Extract by ID")
        dialog.setFixedSize(760, 500)
        
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
