from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from utils.common_components import FASTAWorker, BaseTabWidget
import os


class SequenceStatisticsWorker(FASTAWorker):
    """Sequence length statistics worker"""
    stats_finished = pyqtSignal(dict)  # 统计数据完成信号
    
    def run(self):
        if not self.validate_files():
            return
        
        try:
            self.emit_progress("Loading FASTA file...")
            processor = self.load_fasta_processor()
            if not processor:
                return
            
            self.emit_progress("Computing statistics...")
            records = processor.records
            
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
            
            self.emit_progress("Generating detailed statistics...")
            # 每条序列统计
            stats_lines = ["Sequence_ID\tLength\tGC_Content(%)"]
            for record in records:
                seq_id = record.header.split()[0]
                L = record.length
                # 只计算DNA序列的GC含量
                sequence_upper = record.sequence.upper()
                if all(base in 'ATCGN' for base in sequence_upper):
                    gc = sequence_upper.count('G') + sequence_upper.count('C')
                    gc_content = (gc / L * 100) if L else 0
                    stats_lines.append(f"{seq_id}\t{L}\t{gc_content:.2f}")
                else:
                    stats_lines.append(f"{seq_id}\t{L}\tN/A")
            
            self.emit_progress("Saving results...")
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(stats_lines))
            
            # 发送全局统计数据和完成消息
            self.stats_finished.emit(global_stats)
            self.emit_finished(f"Length statistics complete. Saved to: {self.output_path}")
        except Exception as e:
            self.emit_error(f"Error during length statistics: {e}")


class SequenceStatisticsTab(BaseTabWidget):
    """Sequence length statistics Tab"""
    
    def __init__(self):
        super().__init__("Sequence Statistics", "file")
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
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output stats file:"))
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("Save As")
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
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
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
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
    
    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select FASTA file", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        if file_path:
            self.input_edit.setText(file_path)
            base = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(os.path.join(os.path.dirname(file_path), base + "_length_statistics.txt"))
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save statistics", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.output_edit.setText(file_path)
    
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
        
        valid, error = validate_input_path(input_path, ['.fasta', '.fa', '.fas'])
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        # 启动工作线程
        worker = SequenceStatisticsWorker(input_path, output_path)
        worker.stats_finished.connect(self.update_statistics)
        self.start_worker(worker)
