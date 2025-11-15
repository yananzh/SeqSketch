from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QGridLayout, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class SequenceStatisticsWorker(FASTAWorker):
    """Sequence length statistics worker"""
    # 信号必须定义为类变量，不能在__init__或run中定义
    stats_finished = pyqtSignal(dict)
    
    def __init__(self, input_path: str, output_path: str):
        super().__init__(input_path, output_path)
    
    def run(self):
        import logging
        logger = logging.getLogger(__name__)
        print("=" * 50)
        print("DEBUG: SequenceStatisticsWorker.run() called!")
        print(f"DEBUG: Input path: {self.input_path}")
        print(f"DEBUG: Output path: {self.output_path}")
        print("=" * 50)
        logger.info("SequenceStatisticsWorker.run() started")
        
        try:
            print("DEBUG: Starting file validation...")
            if not self.validate_files():
                print("DEBUG: File validation failed")
                logger.warning("File validation failed")
                return
            
            print("DEBUG: Files validated successfully")
            logger.info("Files validated successfully")
            
            try:
                self.emit_progress("Loading FASTA file...")
                logger.info(f"Loading FASTA file: {self.input_path}")
                processor = self.load_fasta_processor()
                if not processor:
                    logger.error("Failed to load FASTA processor")
                    return
                
                logger.info(f"FASTA file loaded, {len(processor.records)} records")
                
                self.emit_progress("Computing statistics...")
                records = processor.records
                
                if not records:
                    logger.error("No sequences found")
                    self.emit_error("No sequences found in the FASTA file")
                    return
                
                # 全局统计
                total = len(records)
                lengths = [r.length for r in records]
                total_bases = sum(lengths)
                avg_len = total_bases / total if total else 0
                min_len = min(lengths) if lengths else 0
                max_len = max(lengths) if lengths else 0
                
                global_stats = {
                    'total': total,
                    'total_length': total_bases,
                    'avg_len': avg_len,
                    'min_len': min_len,
                    'max_len': max_len
                }
                
                logger.info(f"Global stats computed: {global_stats}")
                
                self.emit_progress("Generating detailed statistics...")
                # 每条序列统计
                stats_lines = ["Sequence_ID\tLength\tGC_Content(%)"]
                allowed = set("ACGTNRYMKSWBDHV")
                for idx, record in enumerate(records):
                    if idx % 100 == 0:
                        logger.info(f"Processing record {idx}/{total}")
                    seq_id = record.header.split()[0]
                    seq = record.sequence.upper().replace('U', 'T')
                    L = len(seq)
                    if L == 0:
                        stats_lines.append(f"{seq_id}\t0\t0.00")
                        continue
                    if all(base in allowed for base in seq):
                        gc = seq.count('G') + seq.count('C')
                        gc_content = (gc / L * 100)
                        stats_lines.append(f"{seq_id}\t{L}\t{gc_content:.2f}")
                    else:
                        # 非标准字符，仍输出长度，GC设为N/A
                        stats_lines.append(f"{seq_id}\t{L}\tN/A")
                
                logger.info(f"Detailed statistics generated for {len(stats_lines)-1} sequences")
                
                self.emit_progress("Saving results...")
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(stats_lines))
                
                logger.info(f"Results saved to: {self.output_path}")
                
                # Emit stats signal with data before finishing
                logger.info("Emitting stats_finished signal")
                self.stats_finished.emit(global_stats)
                
                logger.info("Emitting finished signal")
                self.emit_finished(f"Length statistics complete. Saved to: {self.output_path}")
                logger.info("Worker run() completed successfully")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Error in worker run(): {e}\n{error_details}")
                self.emit_error(f"Error during length statistics: {e}\n{error_details}")
        except Exception as e:
            import traceback
            logger.exception("Unexpected error in worker run()")
            self.emit_error(f"Unexpected error: {e}\n{traceback.format_exc()}")


class SequenceStatisticsTab(BaseTabWidget):
    """Sequence length statistics Tab"""
    
    def __init__(self):
        super().__init__("Sequence Statistics", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # Inner class: LineEdit with file drag-and-drop support
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
                allowed = {'.fasta', '.fa', '.fas', '.fna', '.ffn', '.faa', '.frn', '.txt'}
                try:
                    ext = os.path.splitext(path)[1].lower()
                    return os.path.isfile(path) and ext in allowed
                except Exception:
                    return False

        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input FASTA file:"))
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setMinimumWidth(320)
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.setSpacing(8)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output stats file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the stats...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)
        
        # 全局统计信息显示区
        stats_layout = QGridLayout()
        self.stat_labels = {}
        stats = [
            ("Total Sequences", 'total'),
            ("Total Length", 'total_length'),
            ("Average Length", 'avg_len'),
            ("Min Length", 'min_len'),
            ("Max Length", 'max_len')
        ]
        for i, (label, key) in enumerate(stats):
            row, col = i // 2, (i % 2) * 2
            l = QLabel(f"{label}: ")
            v = QLabel("--")
            v.setStyleSheet("font-weight: bold; color: #2196F3;")
            stats_layout.addWidget(l, row, col)
            stats_layout.addWidget(v, row, col + 1)
            self.stat_labels[key] = v
        # Flexible value columns and nicer spacing
        stats_layout.setColumnStretch(1, 1)
        stats_layout.setColumnStretch(3, 1)
        stats_layout.setHorizontalSpacing(16)
        stats_layout.setVerticalSpacing(6)
        
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
        self.add_content_layout(output_layout)
        self.add_content_layout(stats_layout)
        self.add_content_layout(control_layout)
    
    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_statistics)
        self.clear_btn.clicked.connect(self.clear_all)
        # Drag-and-drop signal from input line edit
        if hasattr(self.input_edit, 'file_dropped'):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FASTA file", "", "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)"
        )
        if file_path:
            self.handle_input_file_selected(file_path)
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save statistics", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)

    def handle_input_file_selected(self, file_path: str):
        """Handle input selection from dialog or drag-and-drop"""
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_length_statistics.txt")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")
    
    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        for label in self.stat_labels.values():
            label.setText("--")
        self.show_status("Cleared")
    
    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
    
    def update_statistics(self, stats: dict):
        """更新统计信息显示"""
        self.stat_labels['total'].setText(str(stats.get('total', 0)))
        self.stat_labels['total_length'].setText(str(stats.get('total_length', 0)))
        self.stat_labels['avg_len'].setText(f"{stats.get('avg_len', 0):.1f}")
        self.stat_labels['min_len'].setText(str(stats.get('min_len', 0)))
        self.stat_labels['max_len'].setText(str(stats.get('max_len', 0)))
    
    def show_help(self):
        """Show help information"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>Sequence Length Statistics</h3>
<p><b>Description:</b></p>
<p>Compute length statistics for sequences in a FASTA file and generate a concise report.</p>

<p><b>Features:</b></p>
<ul>
<li><b>Global stats:</b> total sequences, total length, average, min/max length</li>
<li><b>Detailed report:</b> ID, length, GC content (DNA only) per sequence</li>
</ul>

<p><b>Usage:</b></p>
<ol>
<li>Select a FASTA file (.fasta/.fa/.fas)</li>
<li>Choose where to save the stats file</li>
<li>Click "Start"</li>
<li>View real-time stats and logs</li>
</ol>

<p><b>Output:</b></p>
<p>Generates a TSV file containing ID, length, GC content (%) for DNA sequences (others show N/A).</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Sequence Statistics")
        dialog.setFixedSize(750, 450)
        
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
    
    def run_statistics(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        
        # 验证输入
        from utils.common_components import validate_input_path, validate_output_path
        
        valid, error = validate_input_path(input_path, ['.fasta', '.fa', '.fas', '.fna', '.ffn', '.faa', '.frn', '.txt'])
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        # 禁用按钮，防止重复点击
        self.set_running_state(True)
        self.log_message("Starting sequence statistics processing...", "INFO")
        
        try:
            # 直接在主线程中处理，不使用worker线程
            from modules.fasta_processor import FASTAProcessor
            import os
            
            # 验证输入文件
            if not input_path or not os.path.isfile(input_path):
                self.log_message("Input file is invalid or does not exist", "ERROR")
                self.set_running_state(False)
                return
            
            if not output_path:
                self.log_message("Output file path cannot be empty", "ERROR")
                self.set_running_state(False)
                return
            
            # 检查输出目录是否存在，不存在则创建
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                except Exception as e:
                    self.log_message(f"Unable to create output directory: {e}", "ERROR")
                    self.set_running_state(False)
                    return
            
            # 加载FASTA文件
            self.show_status("Loading FASTA file...")
            self.log_message("Loading FASTA file...", "INFO")
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
            
            self.log_message(f"Successfully loaded {len(records)} sequences", "INFO")
            
            # 计算全局统计
            self.show_status("Computing statistics...")
            self.log_message("Computing statistics...", "INFO")
            
            total = len(records)
            lengths = [r.length for r in records]
            total_bases = sum(lengths)
            avg_len = total_bases / total if total else 0
            min_len = min(lengths) if lengths else 0
            max_len = max(lengths) if lengths else 0
            
            global_stats = {
                'total': total,
                'total_length': total_bases,
                'avg_len': avg_len,
                'min_len': min_len,
                'max_len': max_len
            }
            
            # 更新UI显示统计信息
            self.update_statistics(global_stats)
            self.log_message(f"Total sequences: {total}, Average length: {avg_len:.1f}", "INFO")
            
            # 生成详细统计
            self.show_status("Generating detailed statistics...")
            self.log_message("Generating detailed statistics...", "INFO")
            
            stats_lines = ["Sequence_ID\tLength\tGC_Content(%)"]
            allowed = set("ACGTNRYMKSWBDHV")
            
            for idx, record in enumerate(records):
                seq_id = record.header.split()[0]
                seq = record.sequence.upper().replace('U', 'T')
                L = len(seq)
                
                if L == 0:
                    stats_lines.append(f"{seq_id}\t0\t0.00")
                    continue
                
                if all(base in allowed for base in seq):
                    gc = seq.count('G') + seq.count('C')
                    gc_content = (gc / L * 100)
                    stats_lines.append(f"{seq_id}\t{L}\t{gc_content:.2f}")
                else:
                    # 非标准字符，仍输出长度，GC设为N/A
                    stats_lines.append(f"{seq_id}\t{L}\tN/A")
            
            # 保存结果
            self.show_status("Saving results...")
            self.log_message("Saving results...", "INFO")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(stats_lines))
            
            # 完成
            self.log_message(f"Statistics complete! Results saved to: {output_path}", "INFO")
            self.show_status("Complete")
            
        except Exception as e:
            import traceback
            error_msg = f"Error during processing: {e}\n{traceback.format_exc()}"
            self.log_message(error_msg, "ERROR")
            self.show_status("Error")
        finally:
            # 恢复按钮状态
            self.set_running_state(False)
