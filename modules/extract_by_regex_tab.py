from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog)
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os
import re


class ExtractByRegexWorker(FASTAWorker):
    """Worker to extract sequences by regex"""
    
    def __init__(self, input_path, regex, output_path):
        super().__init__(input_path, output_path)
        self.regex = regex
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("Loading FASTA file...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("Validating regular expression...")
            try:
                pattern = re.compile(self.regex)
            except Exception as e:
                self.emit_error(f"Invalid regular expression: {e}")
                return
            
            self.emit_progress("Matching sequences...")
            matched = []
            for record in processor.records:
                # 用完整ID行（不含>）匹配
                if pattern.search(record.header):
                    matched.append(record)
            
            if not matched:
                self.emit_error("No sequences matched")
                return
            
            self.emit_progress("Saving results...")
            if not processor.save_file(self.output_path, matched):
                self.emit_error("Failed to save file")
                return
            
            self.emit_finished(f"Extraction complete. Found {len(matched)} sequences. Saved to: {self.output_path}")
        except Exception as e:
            self.emit_error(f"Error during extraction: {e}")


class ExtractByRegexTab(BaseTabWidget):
    """Extract by Regex Tab"""
    
    def __init__(self):
        super().__init__("Extract by Regex", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input FASTA file:"))
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton("Browse")
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        
        # 正则表达式输入
        regex_layout = QHBoxLayout()
        regex_layout.addWidget(QLabel("Regular Expression:"))
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText("Examples: gene.*protein, ^chr[0-9]+, .*hypothetical.*")
        regex_layout.addWidget(self.regex_edit)
        
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
        self.add_content_layout(regex_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
    
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
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_regex_extracted.fasta"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save extracted sequences", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.regex_edit.clear()
        self.log_area.clear()
        self.show_status("Cleared")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.regex_edit.setEnabled(not running)
    
    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        regex = self.regex_edit.text().strip()
        
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
        
        if not regex:
            self.log_message("Please enter a regular expression", "ERROR")
            return
        
        # 启动工作线程
        worker = ExtractByRegexWorker(input_path, regex, output_path)
        self.start_worker(worker)
    
    def show_help(self):
        """Show help information"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>Extract by Regular Expression</h3>
<p><b>Description:</b></p>
<p>Use a regex to match sequence IDs and extract matching sequences from a FASTA file.</p>

<p><b>Usage:</b></p>
<ol>
<li>Select the source FASTA file</li>
<li>Choose an output location</li>
<li>Enter a regular expression pattern</li>
<li>Click "Start"</li>
</ol>

<p><b>Regex examples:</b></p>
<ul>
<li><code>^NM_.*</code> - IDs starting with "NM_"</li>
<li><code>.*gene.*</code> - IDs containing "gene"</li>
<li><code>seq_\\d+</code> - IDs like "seq_" followed by digits</li>
<li><code>(protein|enzyme)</code> - IDs containing "protein" or "enzyme"</li>
<li><code>^[A-Z]{2}_\\d{6}$</code> - IDs in format "XX_123456"</li>
</ul>

<p><b>Common regex tokens:</b></p>
<ul>
<li><code>^</code> - start of string</li>
<li><code>$</code> - end of string</li>
<li><code>.*</code> - any characters (greedy)</li>
<li><code>\\d</code> - digits</li>
<li><code>\\w</code> - word characters</li>
<li><code>[A-Z]</code> - uppercase letters</li>
<li><code>+</code> - one or more</li>
<li><code>|</code> - alternation</li>
</ul>

<p><b>Use cases:</b></p>
<ul>
<li>Extract sequences by naming conventions</li>
<li>Filter IDs matching specific formats</li>
<li>Flexible pattern matching and grouping</li>
</ul>

<p><b>Notes:</b></p>
<p>Regex is case-sensitive by default; ensure correctness of your pattern.</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Extract by Regex")
        dialog.setFixedSize(820, 550)
        
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
