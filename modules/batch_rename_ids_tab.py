from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QCheckBox, QSizePolicy)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
import os


# Remove worker, use main thread


class BatchRenameIDsTab(BaseTabWidget):
    """批量重命名序列ID功能Tab"""
    
    def __init__(self):
        super().__init__("Batch Rename IDs", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # 输入FASTA文件选择
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
        
        # 映射文件选择（支持拖放）
        mapping_layout = QHBoxLayout()
        mapping_layout.addWidget(QLabel("ID mapping file:"))
        class MappingDropLineEdit(QLineEdit):
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
                        if self._is_valid_mapping(local):
                            event.acceptProposedAction()
                            return
                event.ignore()
            def dropEvent(self, event):
                urls = event.mimeData().urls()
                if urls:
                    local = urls[0].toLocalFile()
                    if self._is_valid_mapping(local):
                        self.setText(local)
                        self.file_dropped.emit(local)
                        event.acceptProposedAction()
                        return
                event.ignore()
            @staticmethod
            def _is_valid_mapping(path: str) -> bool:
                allowed = {'.csv', '.tsv', '.txt', '.xlsx', '.xls'}
                try:
                    ext = os.path.splitext(path)[1].lower()
                    return os.path.isfile(path) and ext in allowed
                except Exception:
                    return False

        self.mapping_edit = MappingDropLineEdit()
        self.mapping_edit.setPlaceholderText("Select or drop a CSV/TSV mapping file...")
        self.mapping_edit.setMinimumWidth(320)
        self.mapping_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mapping_btn = QPushButton("Choose Mapping File")
        mapping_layout.addWidget(self.mapping_edit)
        mapping_layout.addWidget(self.mapping_btn)
        
        # 映射文件选项
        option_layout = QHBoxLayout()
        self.header_checkbox = QCheckBox("Mapping file contains header row")
        self.header_checkbox.setChecked(True)
        option_layout.addWidget(self.header_checkbox)
        option_layout.addStretch()
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the renamed file...")
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
        self.add_content_layout(mapping_layout)
        self.add_content_layout(option_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.mapping_btn.clicked.connect(self.select_mapping_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_rename)
        self.clear_btn.clicked.connect(self.clear_all)
        if hasattr(self.input_edit, 'file_dropped'):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)
        if hasattr(self.mapping_edit, 'file_dropped'):
            self.mapping_edit.file_dropped.connect(self.handle_mapping_file_selected)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FASTA file", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_renamed.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")
    
    def select_mapping_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ID mapping file", "", 
            "CSV Files (*.csv);;TSV Files (*.tsv *.txt);;All Files (*)"
        )
        if file_path:
            self.handle_mapping_file_selected(file_path)

    def handle_mapping_file_selected(self, file_path: str):
        self.mapping_edit.setText(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xls', '.xlsx']:
            self.log_message("Excel selected. Requires pandas, or save as CSV/TSV.")
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save renamed file", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
    def run_rename(self):
        input_path = self.input_edit.text().strip()
        mapping_path = self.mapping_edit.text().strip()
        output_path = self.output_edit.text().strip()
        has_header = self.header_checkbox.isChecked()

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
        if not mapping_path:
            self.log_message("Please select a mapping file", "ERROR")
            return

        self.set_running_state(True)
        self.log_message("Starting batch ID renaming...", "INFO")
        try:
            ext = os.path.splitext(mapping_path)[1].lower()
            mapping = {}
            if ext in ['.xls', '.xlsx']:
                try:
                    import pandas as pd
                except Exception:
                    self.log_message("Excel mapping requires pandas. Install with: pip install pandas, or save as CSV/TSV.", "ERROR")
                    self.set_running_state(False)
                    return
                df = pd.read_excel(mapping_path, header=0 if has_header else None)
                if df.shape[1] < 2:
                    self.log_message("Mapping file must have at least two columns (old ID, new ID)", "ERROR")
                    self.set_running_state(False)
                    return
                mapping = dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(str)))
            elif ext in ['.csv', '.tsv', '.txt']:
                import csv
                delimiter = ',' if ext == '.csv' else '\t'
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    rows = list(reader)
                if has_header and rows:
                    rows = rows[1:]
                for row in rows:
                    if len(row) >= 2:
                        old_id = str(row[0]).strip()
                        new_id = str(row[1]).strip()
                        if old_id:
                            mapping[old_id] = new_id
                if not mapping:
                    self.log_message("No valid mappings found in the file", "ERROR")
                    self.set_running_state(False)
                    return
            else:
                self.log_message("Unsupported mapping format. Use Excel (.xlsx/.xls), CSV (.csv) or TSV (.tsv/.txt).", "ERROR")
                self.set_running_state(False)
                return
            self.log_message(f"Loaded {len(mapping)} ID mappings", "INFO")
            # Load FASTA
            from modules.fasta_processor import FASTAProcessor
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
            # Rename IDs
            self.show_status("Renaming sequence IDs...")
            total = len(records)
            renamed_count = 0
            for record in records:
                old_id = record.header.split()[0]
                if old_id in mapping:
                    new_id = mapping[old_id]
                    parts = record.header.split(' ', 1)
                    if len(parts) > 1:
                        record.header = f"{new_id} {parts[1]}"
                    else:
                        record.header = new_id
                    renamed_count += 1
            # Save
            self.show_status("Saving results...")
            if not processor.save_file(output_path):
                self.log_message("Failed to save file", "ERROR")
                self.set_running_state(False)
                return
            self.log_message(f"Renaming complete! Processed {total} sequences, renamed {renamed_count}. Saved to: {output_path}", "INFO")
            self.show_status("Complete")
        except Exception as e:
            import traceback
            self.log_message(f"Error during renaming: {e}\n{traceback.format_exc()}", "ERROR")
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def clear_all(self):
        self.input_edit.clear()
        self.mapping_edit.clear()
        self.output_edit.clear()
        self.header_checkbox.setChecked(True)
        if hasattr(self, 'log_area'):
            self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.mapping_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.header_checkbox.setEnabled(not running)
    
    def show_help(self):
        """显示帮助信息"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>批量重命名序列ID工具</h3>
<p><b>功能说明：</b></p>
<p>根据映射文件批量重命名FASTA文件中的序列ID，实现ID的标准化和规范化。</p>

<p><b>使用方法：</b></p>
<ol>
<li>选择要处理的FASTA文件</li>
<li>选择ID映射文件（TSV格式）</li>
<li>设置映射文件是否包含标题行</li>
<li>指定输出文件的保存位置</li>
<li>点击"开始重命名"按钮</li>
</ol>

<p><b>映射文件格式：</b></p>
<p>制表符分隔的文本文件（TSV），包含两列：</p>
<ul>
<li><b>第一列：</b>原始序列ID（与FASTA文件中的ID匹配）</li>
<li><b>第二列：</b>新的序列ID</li>
</ul>

<p><b>映射文件示例：</b></p>
<pre>
原始ID	新ID
sequence_001	Gene_A
sequence_002	Gene_B
NM_001101.5	RefSeq_001
gi|123456|ref|XM_001234.1|	Custom_Gene_X
</pre>

<p><b>标题行选项：</b></p>
<ul>
<li><b>包含标题行：</b>跳过第一行，从第二行开始处理映射关系</li>
<li><b>不含标题行：</b>从第一行开始处理所有映射关系</li>
</ul>

<p><b>处理规则：</b></p>
<ul>
<li>精确匹配原始ID进行替换</li>
<li>未在映射文件中的ID保持不变</li>
<li>重复的新ID会添加后缀以避免冲突</li>
</ul>

<p><b>应用场景：</b></p>
<ul>
<li>序列ID标准化和规范化</li>
<li>将复杂ID替换为简洁的标识符</li>
<li>根据实验设计重新编号序列</li>
<li>数据库迁移时的ID转换</li>
</ul>

<p><b>输出结果：</b></p>
<p>生成新的FASTA文件，序列内容不变，仅更新序列ID。</p>
<p>处理过程会显示重命名的序列数量和详细日志。</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Batch Rename IDs")
        dialog.setFixedSize(850, 550)
        
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
        
        # 添加确定按钮
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec()
