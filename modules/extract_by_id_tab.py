from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QPlainTextEdit, QSizePolicy)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt
from utils.common_components import FASTAWorker, BaseTabWidget
import os


# Remove worker, use main thread


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
        class FileDropLineEdit(QLineEdit):
            file_dropped = pyqtSignal(str)
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setAcceptDrops(True)
            def dragEnterEvent(self, event):
                md = event.mimeData()
                if md.hasUrls():
                    urls = md.urls()
                    if urls:
                        local = urls[0].toLocalFile()
                        if self._is_valid_fasta(local):
                            event.acceptProposedAction()
                            return
                event.ignore()
            def dropEvent(self, event):
                urls = event.mimeData().urls()
                if urls:
                    local = urls[0].toLocalFile()
                    if self._is_valid_fasta(local):
                        self.setText(local)
                        self.file_dropped.emit(local)
                        event.acceptProposedAction()
                        return
                event.ignore()
            @staticmethod
            def _is_valid_fasta(path: str) -> bool:
                allowed = {'.fasta', '.fa', '.fas'}
                try:
                    ext = os.path.splitext(path)[1].lower()
                    return os.path.isfile(path) and ext in allowed
                except Exception:
                    return False

        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setMinimumWidth(320)
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
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
        self.output_edit.setPlaceholderText("Choose where to save the extracted file...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)
        
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
        if hasattr(self.input_edit, 'file_dropped'):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FASTA file", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.handle_input_file_selected(file_path)
    
    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_extracted.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")
    
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

        # Validate input
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
        id_list = [line.strip() for line in id_text.split('\n') if line.strip()]
        if not id_list:
            self.log_message("ID list is empty", "ERROR")
            return

        self.set_running_state(True)
        self.log_message("Starting extraction...", "INFO")
        try:
            from modules.fasta_processor import FASTAProcessor
            import os
            # Load FASTA
            self.show_status("Loading FASTA file...")
            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                self.set_running_state(False)
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                self.set_running_state(False)
                return
            self.log_message(f"Loaded {len(records)} sequences", "INFO")
            # Match IDs
            self.show_status("Matching sequence IDs...")
            id_set = set(id_list)
            matched = [record for record in records if record.header.split()[0] in id_set]
            if not matched:
                self.log_message("No matching IDs found", "ERROR")
                self.set_running_state(False)
                return
            self.log_message(f"Found {len(matched)} matching sequences", "INFO")
            # Save
            self.show_status("Saving results...")
            if not processor.save_file(output_path, matched):
                self.log_message("Failed to save file", "ERROR")
                self.set_running_state(False)
                return
            self.log_message(f"Extraction complete! Saved to: {output_path}", "INFO")
            self.show_status("Complete")
        except Exception as e:
            import traceback
            self.log_message(f"Error during extraction: {e}\n{traceback.format_exc()}", "ERROR")
            self.show_status("Error")
        finally:
            self.set_running_state(False)
    
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
        label.setWordWrap(True)  # 启用自动换行
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
